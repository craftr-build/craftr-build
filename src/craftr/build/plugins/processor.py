
import typing as t
from pathlib import Path

from craftr.build.lib import ExecutableInfo, TaskFactoryExtension
from craftr.core.actions import Action, CreateDirectoryAction, CommandAction
from craftr.core import Namespace, Project, Property, Task


class ProcessorTask(Task):
  inputs: t.Annotated[Property[t.List[Path]], Task.Input]
  outputs: t.Annotated[Property[t.List[Path]], Task.Output]
  additional_vars: t.Annotated[Property[t.Dict[str, t.List[str]]], Task.Input]
  executable: Property[ExecutableInfo]
  args: Property[t.List[str]]
  batch: Property[bool]

  def _render_command(self, executable: ExecutableInfo, template_vars: t.Dict[str, t.List[str]]) -> CommandAction:
    args: t.List[str] = list(executable.invokation_layout or [executable.filename])
    for arg in self.args.or_else([]):
      if arg.startswith('$'):
        varname = arg[1:]
        args.extend(map(str, template_vars[varname]))
      else:
        args.append(arg)
    return CommandAction(args)

  # Task
  def get_actions(self):
    executable = self.executable.get()
    inputs = self.inputs.get()
    outputs = self.outputs.get()
    actions: t.List[Action] = [CreateDirectoryAction(d) for d in set(p.parent for p in outputs)]
    if self.batch.or_else(True):
      if len(inputs) != len(outputs):
        raise ValueError('inputs must be same length as outputs')
      additional_vars = self.additional_vars.or_else({})
      for key, value in additional_vars.items():
        if len(value) != len(inputs):
          raise ValueError(f'additional_vars[{key!r}] must have same length as inputs')
      for index, (infile, outfile) in enumerate(zip(inputs, outputs)):
        template_vars = {k: [v[index]] for k, v in additional_vars.items()}
        template_vars['in'] = [infile]
        template_vars['out'] = [outfile]
        actions.append(self._render_command(executable, template_vars))
    else:
      actions.append(self._render_command(inputs, outputs))
    return actions


def apply(project: Project, namespace: Namespace) -> None:
  namespace.add('ProcessorTask', ProcessorTask)
  namespace.add_task_factory('processor', ProcessorTask)
