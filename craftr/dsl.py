
import collections
import os
import string
import textwrap

from .core import Module
from nr.parse import strex


class Node:
  """
  Represents a node in the Craftr DSL AST.
  """

  def __init__(self, loc):
    if not isinstance(loc, strex.Cursor):
      raise TypeError('expected strex.Cursor')
    self.loc = loc

  def __repr__(self):
    return '<{}@{}>'.format(type(self).__name__, self.loc)


class Project(Node):

  def __init__(self, loc, name, version):
    super().__init__(loc)
    self.name = name
    self.version = version
    self.children = []

  def render(self, fp, depth):
    fp.write('project "{}"'.format(self.name))
    if self.version:
      fp.write(' v{}'.format(self.version))
    fp.write('\n')
    for child in self.children:
      child.render(fp, depth)


class Options(Node):

  DATATYPES = set(['int', 'bool', 'str'])

  @staticmethod
  def adapt(type_name, value):
    if type_name == 'int':
      if isinstance(value, str):
        return int(value)
      elif isinstance(value, int):
        return value
    elif type_name == 'bool':
      if isinstance(value, str):
        value = value.lower().strip()
        if value in ('1', 'true', 'on', 'yes'):
          return True
        elif value in ('0', 'false', 'off', 'no'):
          return False
      elif isinstance(value, bool):
        return value
    elif type_name == 'str':
      if isinstance(value, str):
        return value
    raise TypeError('expected {}, got {}'.format(type_name, type(value).__name__))

  def __init__(self, loc):
    super().__init__(loc)
    self.options = collections.OrderedDict()

  def render(self, fp, depth):
    fp.write('options:\n')
    for key, (type, value) in self.options.items():
      fp.write('  {} {}'.format(type, key))
      if value:
        fp.write(' = ')
        Assignment.render_expression(fp, 2, value)
      else:
        fp.write('\n')


class Eval(Node):

  def __init__(self, loc, source):
    super().__init__(loc)
    self.source = source.rstrip()

  def render(self, fp, depth):
    if '\n' in self.source:
      fp.write('  ' * depth + 'eval:\n')
      for line in self.source.split('\n'):
        fp.write('  ' * (depth+1))
        fp.write(line)
        fp.write('\n')
    else:
      fp.write('  ' * depth + 'eval ')
      fp.write(self.source)
      fp.write('\n')


class Pool(Node):

  def __init__(self, loc, name, depth):
    super().__init__(loc)
    self.name = name
    self.depth = depth

  def render(self, fp, depth):
    fp.write('pool "{}" {}\n'.format(self.name, self.depth))


class Target(Node):

  def __init__(self, loc, name, export):
    super().__init__(loc)
    self.name = name
    self.export = export
    self.children = []  # Requires, Assignment, Eval

  def render(self, fp, depth):
    if self.export:
      fp.write('export ')
    fp.write('target "{}":\n'.format(self.name))
    for child in self.children:
      child.render(fp, depth+1)


class Assignment(Node):

  def __init__(self, loc, name, expression, export):
    super().__init__(loc)
    self.name = name
    self.expression = expression
    self.export = export

  def render(self, fp, depth):
    fp.write('  ' * depth)
    if self.export:
      fp.write('export ')
    fp.write('{} = '.format(self.name))
    self.render_expression(fp, depth+1, self.expression)

  @staticmethod
  def render_expression(fp, depth, expression):
    lines = expression.rstrip().split('\n')
    fp.write(lines[0])
    fp.write('\n')
    for line in lines[1:]:
      fp.write('  ' * depth)
      fp.write(line)
      fp.write('\n')


class Export(Node):

  def __init__(self, loc):
    super().__init__(loc)
    self.assignments = []

  def render(self, fp, depth):
    fp.write('  ' * depth + 'export:\n')
    for assign in self.assignments:
      assign.render(fp, depth+1)


class Dependency(Node):

  def __init__(self, loc, name, export):
    super().__init__(loc)
    self.name = name
    self.export = export
    self.assignments = []

  def render(self, fp, depth):
    fp.write('  ' * depth)
    if self.export:
      fp.write('export ')
    fp.write('dependency "{}"'.format(self.name))
    fp.write(':\n' if self.assignments else '\n')
    for assign in self.assignments:
      assign.render(fp, depth+1)


class Parser:

  rules = [
    strex.Regex('comment', '#.*', skip=True),
    strex.Regex('string', '"([^"]*)"'),
    strex.Regex('string', "'([^']*)'"),
    strex.Regex('version', 'v(\d+\.\d+\.\d+)'),
    strex.Charset('number', string.digits),
    strex.Charset('name', string.ascii_letters + string.digits + '_'),
    strex.Keyword('=', '='),
    strex.Keyword(':', ':'),
    strex.Keyword('.', '.'),
    strex.Charset('nl', '\n'),
    strex.Charset('ws', '\t ', skip=True),
  ]

  KEYWORDS = ['project', 'options', 'eval', 'pool', 'export', 'target', 'dependency']

  def parse(self, source):
    lexer = strex.Lexer(strex.Scanner(source), self.rules)
    # TODO: Catch TokenizationError, UnexpectedTokenError
    try:
      return self._parse_project(lexer)
    except strex.TokenizationError as e:
      raise ParseError(e.token.cursor, repr(e.token.value))
    except strex.UnexpectedTokenError as e:
      raise ParseError(e.token.cursor, 'unexpected token "{}"'.format(e.token.type))

  def _skip(self, lexer):
    while lexer.accept('nl'):
      pass

  def _parse_project(self, lexer):
    self._skip(lexer)
    token = lexer.next('name')
    if token.value != 'project':
      raise ParseError(token.cursor, 'expected keyword "project"')
    loc = token.cursor
    name = lexer.next('string').value.group(1)
    token = lexer.accept('version')
    version = token.value.group(1) if token else '1.0.0'
    lexer.next('nl', 'eof')
    project = Project(loc, name, version)
    self._skip(lexer)
    while lexer.token.type != 'eof':
      project.children.append(self._parse_stmt_or_block(lexer))
      self._skip(lexer)
    return project

  def _parse_stmt_or_block(self, lexer, keywords=None, parent_indent=None, export=False):
    if keywords is None:
      keywords = self.KEYWORDS
    token = lexer.next('name', 'eof')
    if token.type == 'eof':
      return None
    loc = token.cursor

    # This was not prefixed by "export".
    if not export:
      if (parent_indent is None and loc.colno != 0):
        raise ParseError(loc, 'unexpected indent')
      if (parent_indent is not None and loc.colno <= parent_indent):
        # Needs to be parsed in a different context.
        lexer.scanner.restore(loc)
        return None
      parent_indent = loc.colno

    if 'export' in keywords and token.value == 'export' and not lexer.accept(':'):
      if export:
        raise ParseError(loc, 'unexpected keyword "export"')
      sub_keywords = []
      if 'target' in keywords: sub_keywords.append('target')
      if 'dependency' in keywords: sub_keywords.append('dependency')
      return self._parse_stmt_or_block(lexer, sub_keywords, parent_indent, export=True)
    if token.value == 'export' and lexer.token.type == ':':
      lexer.scanner.restore(lexer.token.cursor)

    if token.value in keywords:
      return getattr(self, '_parse_' + token.value)(lexer, parent_indent=parent_indent, export=export)
    elif token.value in self.KEYWORDS:
      raise ParseError(loc, 'unexpected keyword "{}"'.format(token.value))
    scope = token.value
    lexer.next('.')
    propname = lexer.next('name').value
    lexer.next('=')
    value = self._parse_expression(lexer, parent_indent)
    lexer.next('nl', 'eof')
    return Assignment(loc, scope + '.' + propname, value, export)

  def _parse_expression(self, lexer, parent_indent):
    if lexer.scanner.colno == 0:
      first_line = None
    else:
      first_line = lexer.scanner.readline()
    sub_lines = []
    min_indent = 10*3
    while True:
      loc = lexer.scanner.cursor
      match = lexer.scanner.match('[\t ]+')
      if not match or len(match.group(0)) <= parent_indent:
        lexer.scanner.restore(loc)
        break
      sub_lines.append(match.group(0) + lexer.scanner.readline())
      min_indent = min(min_indent, len(match.group(0)))
    # Restore the last new-line, as it serves as statement delimiter.
    if (not sub_lines and first_line.endswith('\n')) or \
        (sub_lines and sub_lines[-1].endswith('\n')):
      lexer.scanner.seek(-1, 'cur')
    result = textwrap.dedent(''.join(sub_lines))
    if first_line:
      result = first_line.lstrip() + result
    return result

  def _parse_options(self, lexer, parent_indent, export):
    assert not export
    options = Options(lexer.token.cursor)
    lexer.next(':')
    lexer.next('nl')
    while True:
      token = lexer.next('name', 'eof')
      if token.type == 'eof' or token.cursor.colno <= parent_indent:
        lexer.scanner.restore(token.cursor)
        break  # Needs to be parsed in a different context
      loc = token.cursor
      dtype = token.value
      if dtype not in Options.DATATYPES:
        raise ParseError(token.cursor, 'expected ' + str(set(Options.DATATYPES)))
      token = lexer.next('name')
      if token.value in options.options:
        raise ParseError(token.cursor, 'duplicate option {!r}'.format(token.value))
      name = token.value
      token = lexer.accept('=')
      if token:
        value = self._parse_expression(lexer, loc.colno)
      else:
        value = None
      options.options[name] = (dtype, value)
      lexer.next('nl', 'eof')
    if not options.options:
      raise ParseError(lexer.token.cursor, 'expected at least one indented statement')
    return options

  def _parse_eval(self, lexer, parent_indent, export):
    assert not export
    loc = lexer.token.cursor
    if lexer.accept(':'):
      lexer.next('nl')
    return Eval(loc, self._parse_expression(lexer, loc.colno))

  def _parse_pool(self, lexer, parent_indent, export):
    assert not export
    loc = lexer.token.cursor
    name = lexer.next('string').value.group(1)
    depth = int(lexer.next('number').value)
    lexer.next('nl', 'eof')
    return Pool(loc, name, depth)

  def _parse_target(self, lexer, parent_indent, export):
    loc = lexer.token.cursor
    name = lexer.next('string').value.group(1)
    lexer.next(':')
    lexer.next('nl')
    subblocks = ['dependency', 'eval', 'export']
    target = Target(loc, name, export)
    while True:
      self._skip(lexer)
      child = self._parse_stmt_or_block(lexer, subblocks, parent_indent)
      if not child: break
      target.children.append(child)
    return target

  def _parse_dependency(self, lexer, parent_indent, export):
    name = lexer.next('string').value.group(1)
    dep = Dependency(lexer.token.cursor, name, export)
    if lexer.accept(':'):
      lexer.next('nl')
      while True:
        self._skip(lexer)
        child = self._parse_stmt_or_block(lexer, [], parent_indent)
        if not child: break
        assert isinstance(child, Assignment)
        dep.assignments.append(child)
    else:
      lexer.next('nl', 'eof')
    return dep

  def _parse_export(self, lexer, parent_indent, export):
    assert not export
    export = Export(lexer.token.cursor)
    lexer.next(':')
    while True:
      self._skip(lexer)
      child = self._parse_stmt_or_block(lexer, [], parent_indent)
      if not child: break
      assert isinstance(child, Assignment)
      export.assignments.append(child)
    return export


class ParseError(Exception):

  def __init__(self, loc, message):
    self.loc = loc
    self.message = message

  def __str__(self):
    return 'line {}, col {}: {}'.format(self.loc.lineno, self.loc.colno, self.message)


class Context:

  def get_option(self, module_name, option_name):
    raise NotImplementedError


class Interpreter:
  """
  Interpreter for projects.
  """

  def __init__(self, context, filename):
    self.context = context
    self.filename = filename
    self.directory = os.path.dirname(filename)

  def __call__(self, project):
    module = self.create_module(project)
    self.eval_module(project, module)
    return module

  def create_module(self, project):
    return Module(project.name, project.version, self.directory)

  def eval_module(self, project, module):
    for node in project.children:
      if isinstance(node, Eval):
        self._exec(node.loc.lineno, node.source, module.eval_namespace())
      elif isinstance(node, Options):
        for key, (type, value) in node.options.items():
          try:
            has_value = self.context.get_option(module.name(), key)
          except KeyError:
            if value is None:
              raise MissingRequiredOptionError(module.name(), key)
            has_value = self._eval(node.loc.lineno, value, module.eval_namespace())
          try:
            has_value = Options.adapt(type, has_value)
          except ValueError as exc:
            raise InvalidOptionError(module.name(), key, str(exc))
          # Publish the option value to the module's namespace.
          setattr(module.eval_namespace(), key, has_value)

  def _exec(self, lineno, source, namespace):
    source = '\n' * (lineno-1) + source
    code = compile(source, self.filename, 'exec')
    exec(code, vars(namespace), vars(namespace))


class RunError(Exception):
  pass


class OptionError(RunError):

  def __init__(self, module_name, option_name, message=None):
    self.module_name = module_name
    self.option_name = option_name
    self.message = message

  def __str__(self):
    result = '{}.{}'.format(self.module_name, self.option_name)
    if self.message:
      result += ': ' + str(self.message)
    return result


class MissingRequiredOptionError(OptionError):
  pass


class InvalidOptionError(OptionError):
  pass
