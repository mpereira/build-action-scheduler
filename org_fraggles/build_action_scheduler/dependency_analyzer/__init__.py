from queue import PriorityQueue
from typing import Any, Dict, Optional, Set, Tuple

from pydantic import BaseModel, PrivateAttr

from org_fraggles.build_action_scheduler.types import Action, Sha1


class CriticalPaths(BaseModel):
    # Mapping of SHA-1 strings to action objects.
    actions_by_sha1: Dict[Sha1, Action]

    # An inverse mapping of dependencies to dependents.
    #
    # E.g., if both 'B' and 'C' depend on 'A', then {'A': {'B', 'C'}}
    action_dependents: Dict[Sha1, Set[Sha1]]

    # Priority queue to store paths and their durations.
    _priority_queue: PriorityQueue = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)

        self._priority_queue = PriorityQueue()

        all_actions = set(self.actions_by_sha1.keys())
        actions_with_dependencies = set(
            dep for deps in self.action_dependents.values() for dep in deps
        )
        starting_nodes = all_actions - actions_with_dependencies

        # Enqueue initial paths from starting nodes.
        for start_action_sha1 in starting_nodes:
            self._priority_queue.put(
                (self.actions_by_sha1[start_action_sha1].duration, [start_action_sha1])
            )

        terminal_paths = []
        while not self._priority_queue.empty():
            current_duration, path = self._priority_queue.get()
            last_node = path[-1]

            if last_node not in self.action_dependents:
                terminal_paths.append((current_duration, path))
            else:
                for neighbor in self.action_dependents[last_node]:
                    new_duration = (
                        current_duration + self.actions_by_sha1[neighbor].duration
                    )
                    new_path = path + [neighbor]
                    self._priority_queue.put((new_duration, new_path))

        # Enqueue terminal paths back into the priority queue
        for duration, path in terminal_paths:
            self._priority_queue.put((-1 * duration, path))

    def empty(self) -> bool:
        return self._priority_queue.empty()

    def current_most_critical(self) -> Optional[Tuple[int, Any]]:
        v = self._priority_queue.get()

        if v is None:
            return None

        return (v[0] * -1, v[1])


class DependencyAnalyzerError(Exception):
    """Parent exception for exceptions raised by the DependencyAnalyzer."""

    def __init__(self, message: Optional[str] = "") -> None:
        """Creates an instance of DependencyAnalyzerError."""
        super().__init__(message)


class DependencyCycleError(DependencyAnalyzerError):
    """Raised when there is a dependency cycle."""


class DependencyAnalyzer(BaseModel):
    # Mapping of SHA-1 strings to action objects.
    actions_by_sha1: Dict[Sha1, Action]

    # An inverse mapping of dependencies to dependents.
    #
    # E.g., if both 'B' and 'C' depend on 'A', then {'A': {'B', 'C'}}
    action_dependents: Dict[Sha1, Set[Sha1]]

    # Priority queue to store paths and their durations.
    _critical_paths: Optional[CriticalPaths] = PrivateAttr(default=None)

    def critical_paths(self) -> CriticalPaths:
        """Calculates the critical paths for the actions.

        Returns:
            CriticalPaths: The critical paths for the actions.

        Raises:
            DependencyCycleError: If there is a dependency cycle.
        """
        if self._critical_paths:
            return self._critical_paths

        if self.detect_cycle():
            raise DependencyCycleError("There is a dependency cycle")

        self._critical_paths = CriticalPaths(
            actions_by_sha1=self.actions_by_sha1,
            action_dependents=self.action_dependents,
        )

        return self._critical_paths

    def detect_cycle(self):
        visited = set()
        action_path = set()

        def dfs(action_sha1):
            if action_sha1 in action_path:
                return True

            if action_sha1 in visited:
                return False

            visited.add(action_sha1)
            action_path.add(action_sha1)

            for dependency_sha1 in self.actions_by_sha1[action_sha1].dependencies:
                if dfs(dependency_sha1):
                    return True

            action_path.remove(action_sha1)

            return False

        for action_sha1 in self.actions_by_sha1:
            if action_sha1 not in visited:
                if dfs(action_sha1):
                    return True

        return False
