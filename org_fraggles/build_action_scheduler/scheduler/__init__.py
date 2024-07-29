from typing import Any, Dict, List

from pydantic import BaseModel

from org_fraggles.build_action_scheduler.dependency_analyzer import (
    CriticalPath,
    CriticalPaths,
    DependencyAnalyzer,
    DependencyCycleError,
)
from org_fraggles.build_action_scheduler.executor import ActionExecutor
from org_fraggles.build_action_scheduler.types import Action, Sha1


class ActionScheduler(BaseModel):
    # The maximum number of actions to execute in parallel.
    parallelism: int

    # The actions to schedule and execute.
    actions: List[Action]

    # Mapping of SHA-1 strings to action objects.
    actions_by_sha1: Dict[Sha1, Action]

    # The action executor.
    action_executor: ActionExecutor

    # The dependency analyzer.
    dependency_analyzer: DependencyAnalyzer

    def schedule(self) -> Dict[str, Any]:
        """Schedules the actions for execution."""
        action_cache = {}
        action_executions = []

        try:
            critical_paths = self.dependency_analyzer.critical_paths()
        except DependencyCycleError:
            return {"error": "Dependency cycle detected"}

        overall_critical_path = critical_paths.peek()

        while not critical_paths.empty():
            current_critical_path = critical_paths.pop()
            _, path = current_critical_path

            action_with_no_dependencies = path[0]

            if action_with_no_dependencies in action_cache:
                if len(path) > 1:
                    self._acknowledge_critical_path_action_execution(
                        critical_paths, current_critical_path
                    )

                continue

            result = self.action_executor.execute(action_with_no_dependencies)

            action_cache[action_with_no_dependencies] = result
            action_executions.append(action_with_no_dependencies)

            if len(path) > 1:
                self._acknowledge_critical_path_action_execution(
                    critical_paths, current_critical_path
                )

        return {
            "linearizable_action_executions": action_executions,
            "critical_path": {
                "duration": overall_critical_path[0],
                "path": overall_critical_path[1],
            },
        }

    def _acknowledge_critical_path_action_execution(
        self, critical_paths: CriticalPaths, critical_path: CriticalPath
    ):
        duration, path = critical_path
        action_executed = path[0]
        critical_paths.push(
            (
                duration - self.actions_by_sha1[action_executed].duration,
                path[1:],
            )
        )
