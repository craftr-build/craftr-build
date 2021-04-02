
import abc
import typing as t

if t.TYPE_CHECKING:
  from kahmi.core.system.project import Project
  from kahmi.core.system.task import Task


class TaskSelector(metaclass=abc.ABCMeta):
  """ An interface to expand a string into a set of tasks in the context of a project. """

  @abc.abstractproperty
  def select_tasks(self, selection: str, project: 'Project') -> t.Collection['Task']:
    pass

  @abc.abstractproperty
  def select_default(self, project: 'Project') -> t.Collection['Task']:
    pass


class DefaultTaskSelector(TaskSelector):
  """
  The default task selector employs the following selector syntax:

      [:][subProject:]+[taskName]

  If the selector is prefixed with a semi-colon (`:`), the task path must be exact and relative
  to the current project. The `taskName` may refer to an individial task's name or a task group.

  Without the `:` prefix, the path must only match exactly at the end of the path (e.g. `a:b`
  matches both tasks with an absolute path `foo:a:b` and `egg:spam:a:b`).
  """

  def select_tasks(self, selection: str, project: 'Project') -> t.Collection['Task']:
    is_abs = selection.startswith(':')
    if not is_abs:
      selection = ':' + selection

    result: t.Set[Task] = set()
    for task in self._iter_all_tasks(project):
      if self._matches(task.path, selection, is_abs):
        result.add(task)
      elif task.group and self._matches(task.project.path + ':' + task.group, selection, is_abs):
        result.add(task)

    return result

  def select_default(self, project: 'Project') -> t.Collection['Task']:
    result: t.Set[Task] = set()
    for task in self._iter_all_tasks(project):
      if task.default:
        result.add(task)
    return result

  def _iter_all_tasks(self, project: 'Project') -> t.Iterator['Task']:
    yield from project.tasks()
    for subproject in project.subprojects():
      yield from self._iter_all_tasks(subproject)

  def _matches(self, path: str, semantic_selection: str, is_abs: bool) -> bool:
    if not is_abs and path == semantic_selection.lstrip(':'):
      return True
    if not path.endswith(semantic_selection):
      return False
    if is_abs and path[:-len(semantic_selection)].count(':') != 0:
      return False
    return True
