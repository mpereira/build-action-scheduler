from queue import PriorityQueue
from typing import Tuple

from pydantic import BaseModel, PrivateAttr

from org_fraggles.build_action_scheduler.actions_info import ActionsInfo
from org_fraggles.build_action_scheduler.types import ActionPath

CriticalPath = Tuple[int, ActionPath]


class CriticalPaths(BaseModel):
    # Actions info.
    actions_info: ActionsInfo

    # Priority queue to store paths and their durations.
    _critical_paths: PriorityQueue = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)
        self._initialize_critical_paths()

    def empty(self) -> bool:
        """Returns True if the priority queue is empty, False otherwise."""
        return self._critical_paths.empty()

    def peek(self) -> CriticalPath | None:
        """Returns the most critical path without removing it from the priority queue."""
        critical_path = self.pop()
        if critical_path:
            self.push(critical_path)
        return critical_path

    def pop(self) -> CriticalPath | None:
        """Removes and returns the most critical path from the priority queue."""
        v = self._critical_paths.get()

        if v is None:
            return None

        return (v[0] * -1, v[1])

    def push(self, duration_and_path: CriticalPath) -> None:
        """Pushes a path with its duration onto the priority queue.

        Since priority queues are min-heaps, we negate the duration to get the
        most critical path when popping.

        Args:
            duration_and_path: The duration and path to push onto the priority queue.
        """
        return self._critical_paths.put(
            (duration_and_path[0] * -1, duration_and_path[1])
        )

    def _initialize_critical_paths(self) -> None:
        """Initializes the priority queue with the `(duration, path)` tuples.

        All paths will have their first elements as leaf actions (no dependencies)
        and last elements as root actions (no dependents).
        """
        self._critical_paths = PriorityQueue()

        all_actions = set(self.actions_info.actions_by_sha1.keys())
        actions_with_dependencies = set(
            action_sha1
            for action_sha1, action in self.actions_info.actions_by_sha1.items()
            if action.dependencies
        )
        leaf_actions = all_actions - actions_with_dependencies

        for leaf_action_sha1 in leaf_actions:
            self._critical_paths.put(
                (
                    self.actions_info.actions_by_sha1[leaf_action_sha1].duration,
                    [leaf_action_sha1],
                )
            )

        all_paths = []

        while not self._critical_paths.empty():
            duration, path = self._critical_paths.get()
            path_last_action = path[-1]

            if path_last_action in self.actions_info.action_dependents:
                # Some action depends on this action, so it is between the leaf
                # and the root. Add it to the path and increment the path
                # duration with its duration.
                for dependent in self.actions_info.action_dependents[path_last_action]:
                    new_duration = (
                        duration + self.actions_info.actions_by_sha1[dependent].duration
                    )
                    new_path = path + [dependent]
                    self._critical_paths.put((new_duration, new_path))
            else:
                # No action depends on this one, so we end the path and add it
                # to the list.
                all_paths.append((duration, path))

        for duration, path in all_paths:
            self._critical_paths.put((-1 * duration, path))


class DependencyAnalyzerError(Exception):
    """Parent exception for exceptions raised by the DependencyAnalyzer."""

    def __init__(self, message: str | None = "") -> None:
        """Creates an instance of DependencyAnalyzerError."""
        super().__init__(message)


class DependencyCycleError(DependencyAnalyzerError):
    """Raised when there is a dependency cycle."""


class DependencyAnalyzer(BaseModel):
    # Actions info.
    actions_info: ActionsInfo

    # Priority queue to store paths and their overall durations.
    _critical_paths: CriticalPaths | None = PrivateAttr(default=None)

    def critical_paths(self) -> CriticalPaths:
        """Calculates the critical paths and their overall durations.

        Returns:
            CriticalPaths: The critical paths for the actions.

        Raises:
            DependencyCycleError: If there is a dependency cycle.
        """
        if self._critical_paths:
            return self._critical_paths

        if self.detect_cycle():
            raise DependencyCycleError("There is a dependency cycle")

        self._critical_paths = CriticalPaths(actions_info=self.actions_info)

        return self._critical_paths

    def detect_cycle(self) -> bool:
        """Returns True if there is a cycle in the dependency graph, False otherwise.

        Uses depth-first search to detect cycles by checking if a node being
        visited is already in the tree/graph path.
        """
        visited = set()
        action_path = set()

        def dfs(action_sha1):
            if action_sha1 in action_path:
                return True

            if action_sha1 in visited:
                return False

            visited.add(action_sha1)
            action_path.add(action_sha1)

            for dependency_sha1 in self.actions_info.actions_by_sha1[
                action_sha1
            ].dependencies:
                if dfs(dependency_sha1):
                    return True

            action_path.remove(action_sha1)

            return False

        for action_sha1 in self.actions_info.actions_by_sha1:
            if action_sha1 not in visited:
                if dfs(action_sha1):
                    return True

        return False
