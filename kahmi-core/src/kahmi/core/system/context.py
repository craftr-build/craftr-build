
import os
import sys
import typing as t
from pathlib import Path

from nr.caching.api import NamespaceStore

from kahmi.core.executor import Executor
from kahmi.core.system.executiongraph import ExecutionGraph
from kahmi.core.system.project import Project
from kahmi.core.system.task import Task
from kahmi.core.system.taskselector import TaskSelector
from kahmi.core.util.caching import JsonDirectoryStore
from kahmi.core.util.config import Config
from kahmi.core.util.preconditions import check_instance_of
from kahmi.core.util.pyimport import load_class


class Context:
  """
  The context carries globally accessible data for a Kahmi build. If not *settings* are specified,
  the `kahmi.properties` file is read from the current working directory (if it exists).

  # Supported Settings

  * `core.build_directory` (no default)
  * `core.executor` (defaults to `kahmi.core.executor.simple.SimpleExecutor`)
  * `core.task_selector` (defaults to `kahmi.core.system.taskselector.DefaultTaskSelector`)
  """

  DEFAULT_EXECUTOR = 'kahmi.core.executor.simple.SimpleExecutor'
  DEFAULT_SELECTOR = 'kahmi.core.system.taskselector.DefaultTaskSelector'
  KAHMI_PROPERTIES_FILE = Path('kahmi.properties')

  def __init__(self, executor: t.Optional[Executor] = None, settings: t.Optional[Config] = None) -> None:
    self._root_project: t.Optional[Project] = None

    if settings is None and self.KAHMI_PROPERTIES_FILE.exists():
      settings = Config.parse(self.KAHMI_PROPERTIES_FILE.read_text().splitlines())
    elif settings is None:
      settings = Config.of({})

    if executor is None:
      executor_class = load_class(settings.get('core.executor', self.DEFAULT_EXECUTOR))
      executor = t.cast(Executor, executor_class(settings))
      check_instance_of(executor, Executor)

    self.settings = settings
    self.executor = executor
    self.graph = ExecutionGraph()
    self.metadata_store: NamespaceStore = JsonDirectoryStore('.kahmi/metadata', create_dir=True)

  @property
  def root_project(self) -> t.Optional[Project]:
    return self._root_project

  def project(self, directory: t.Optional[str] = None) -> Project:
    """
    Initialize the root project and return it. If no directory is specified, the parent directory
    of the caller's filename is used.
    """

    if self._root_project:
      raise RuntimeError('root project already initialized')

    if directory is None:
      directory = os.path.dirname(sys._getframe(1).f_code.co_filename)

    project = Project(self, None, directory)
    self._root_project = project
    self.initialize_project(project)
    return project

  def initialize_project(self, project: Project) -> None:
    """
    Called when a project is created. Can be overwritten by subclasses to customize what happens
    when a project is created.
    """

    pass

  def get_default_build_directory(self, project: Project) -> Path:
    """
    Returns the default build directory for a project, used if no explicit build directory is
    set. The default implementation returns the `.build/` directory in the project's directory,
    unless `core.build_directory` is set.
    """

    build_directory = self.settings.get('core.build_directory', None)
    if build_directory is None:
      return project.directory.joinpath('.build')
    else:
      return Path(build_directory)

  def execute(self, selection: t.Union[None, str, t.List[str], Task, t.List[Task]] = None) -> None:
    selector_class = load_class(self.settings.get('core.task_selector', self.DEFAULT_SELECTOR))
    selector = t.cast(TaskSelector, selector_class())
    check_instance_of(selector, TaskSelector)

    selected_tasks: t.Set[Task] = set()

    if selection is None:
      selected_tasks.update(selector.select_default(self.root_project))
    else:
      if isinstance(selection, (str, Task)):
        selection = [selection]
      for item in selection:
        if isinstance(item, Task):
          selected_tasks.add(item)
        elif isinstance(item, str):
          result_set = selector.select_tasks(item, self.root_project)
          if not result_set:
            raise ValueError(f'selector matched no tasks: {item!r}')
          selected_tasks.update(result_set)
        else:
          raise TypeError(f'expected str|Task, got {type(item).__name__}')

    self.graph.add_tasks(selected_tasks)
    self.graph.ready()
    self.executor.execute(self.graph)
