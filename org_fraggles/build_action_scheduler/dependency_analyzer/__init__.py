from queue import PriorityQueue
from typing import Any, Dict, Set, Tuple

from pydantic import BaseModel, PrivateAttr

from org_fraggles.build_action_scheduler.types import Action, Sha1

CriticalPath = Tuple[int, Any]


class CriticalPaths(BaseModel):
    # Mapping of SHA-1 strings to action objects.
    actions_by_sha1: Dict[Sha1, Action]

    # An inverse mapping of dependencies to dependents.
    #
    # E.g., if both 'B' and 'C' depend on 'A', then {'A': {'B', 'C'}}
    action_dependents: Dict[Sha1, Set[Sha1]]

    # Priority queue to store paths and their durations.
    _critical_paths: PriorityQueue = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)
        self._initialize_critical_paths()

    def empty(self) -> bool:
        return self._critical_paths.empty()

    def peek(self) -> CriticalPath | None:
        critical_path = self.pop()
        if critical_path:
            self.push(critical_path)
        return critical_path

    def pop(self) -> CriticalPath | None:
        v = self._critical_paths.get()

        if v is None:
            return None

        return (v[0] * -1, v[1])

    def push(self, duration_and_path: CriticalPath) -> None:
        return self._critical_paths.put(
            (duration_and_path[0] * -1, duration_and_path[1])
        )

    def _initialize_critical_paths(self) -> None:
        """Initializes the priority queue with the (path duration, path) tuples."""
        self._critical_paths = PriorityQueue()

        all_actions = set(self.actions_by_sha1.keys())
        actions_with_dependencies = set(
            dep for deps in self.action_dependents.values() for dep in deps
        )
        leaf_actions = all_actions - actions_with_dependencies

        for leaf_action_sha1 in leaf_actions:
            self._critical_paths.put(
                (self.actions_by_sha1[leaf_action_sha1].duration, [leaf_action_sha1])
            )

        paths_starting_with_leaves = []
        while not self._critical_paths.empty():
            duration, path = self._critical_paths.get()
            path_last_action = path[-1]

            if path_last_action not in self.action_dependents:
                paths_starting_with_leaves.append((duration, path))
            else:
                for neighbor in self.action_dependents[path_last_action]:
                    new_duration = duration + self.actions_by_sha1[neighbor].duration
                    new_path = path + [neighbor]
                    self._critical_paths.put((new_duration, new_path))

        for duration, path in paths_starting_with_leaves:
            self._critical_paths.put((-1 * duration, path))


class DependencyAnalyzerError(Exception):
    """Parent exception for exceptions raised by the DependencyAnalyzer."""

    def __init__(self, message: str | None = "") -> None:
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
    _critical_paths: CriticalPaths | None = PrivateAttr(default=None)

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
