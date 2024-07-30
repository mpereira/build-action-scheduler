import logging
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any, Deque, Dict, List, Set

from pydantic import BaseModel, PrivateAttr

from org_fraggles.build_action_scheduler.actions_info import ActionsInfo
from org_fraggles.build_action_scheduler.dependency_analyzer import (
    CriticalPath,
    CriticalPaths,
    DependencyAnalyzer,
    DependencyCycleError,
)
from org_fraggles.build_action_scheduler.types import ActionDuration, ActionSha1

log = logging.getLogger(__name__)

Timestamp = str


class ActionScheduler(BaseModel):
    # The maximum number of actions to be executing in parallel at any given time.
    parallelism: int

    # The interval in seconds to poll for actions ready to be scheduled.
    action_status_polling_interval_s: int

    # Actions info.
    actions_info: ActionsInfo

    # The dependency analyzer.
    dependency_analyzer: DependencyAnalyzer

    # Priority queue to store paths and their overall durations.
    _critical_paths: CriticalPaths = PrivateAttr(default=None)

    # Keeps track of the number of pending dependencies for each action.
    _action_pending_dependencies_count: Dict[ActionSha1, int] = PrivateAttr(
        default=defaultdict(int)
    )

    # Holds the results for actions that have been executed.
    _action_cache: Dict[ActionSha1, Any] = PrivateAttr(default_factory=dict)

    # Actions that are running at a certain time.
    _actions_running: Set[ActionSha1] = PrivateAttr(default_factory=set)

    # A linear history of action execution starts.
    _action_execution_start_history: List[ActionSha1] = PrivateAttr(
        default_factory=list
    )

    # A linear history of action execution ends.
    _action_execution_end_history: List[ActionSha1] = PrivateAttr(default_factory=list)

    _lock: Lock = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)

        # Set initial number of pending dependencies for each action.
        self._action_pending_dependencies_count = (
            self.actions_info.action_dependencies_count
        )

        self._lock = Lock()

    def schedule(self) -> Dict[str, Any]:
        """Schedules actions for execution, possibly in parallel.

        Returns:
            An error dict in case of errors, or a dict containing scheduling results.
        """
        ready_actions = deque([])

        try:
            self._critical_paths = self.dependency_analyzer.critical_paths()
        except DependencyCycleError:
            return {"error": "Dependency cycle detected"}

        overall_critical_path = self._critical_paths.peek()

        with ThreadPoolExecutor(max_workers=self.parallelism) as executor:
            while not self._critical_paths.empty():
                for action in self._find_next_ready_actions():
                    ready_actions.appendleft(action)

                actions_submitted = self._submit_as_many_as_possible(
                    executor, ready_actions
                )

                if len(actions_submitted) == 0:
                    self._log_current_status()
                    time.sleep(self.action_status_polling_interval_s)

                    continue

        return {
            "action_execution_history": self._action_execution_start_history,
            "critical_path": {
                "duration": overall_critical_path[0],
                "path": overall_critical_path[1],
            },
        }

    def execute(self, action_sha1: ActionSha1) -> ActionDuration:
        """Executes a given action.

        For now, all actions are "sleep" actions, so executing them means
        sleeping for their duration.

        Args:
            action: The action to execute.

        Returns:
            The duration of the action.
        """
        self._on_action_execution_start(action_sha1)

        duration = self.actions_info.actions_by_sha1[action_sha1].duration
        time.sleep(duration)

        self._on_action_execution_done(action_sha1, duration)

        return duration

    def _find_next_ready_actions(self) -> List[ActionSha1]:
        """Iterates over the critical paths and returns the actions that are ready to be executed.

        Actions are ready to be executed if they have no pending dependencies.

        Returns:
            A list of actions that are ready to be executed.
        """
        ready_actions = []
        # NOTE: using a set in conjunction with a list to ensure that there are
        # no duplicates in the returned actions.
        ready_actions_set = set()

        # These will be paths whose first action is not ready to be executed
        # yet.
        critical_paths_not_ready = []

        while not self._critical_paths.empty():
            current_critical_path = self._critical_paths.pop()
            _, path = current_critical_path

            maybe_ready_action = path[0]

            if maybe_ready_action in self._action_cache:
                self._reinsert_critical_path_tail(current_critical_path)

                continue

            if self._action_pending_dependencies_count[maybe_ready_action] > 0:
                critical_paths_not_ready.append(current_critical_path)
                continue

            if maybe_ready_action not in ready_actions_set:
                with self._lock:
                    ready_actions.append(maybe_ready_action)
                    ready_actions_set.add(maybe_ready_action)

                    self._reinsert_critical_path_tail(current_critical_path)

        with self._lock:
            for critical_path in critical_paths_not_ready:
                self._critical_paths.push(critical_path)

        return ready_actions

    def _submit_as_many_as_possible(
        self, executor: ThreadPoolExecutor, action_sha1s: Deque[ActionSha1]
    ) -> List[ActionSha1]:
        """Submits as many actions as possible to the executor based on its current capacity.

        Args:
            executor: The executor to submit actions to.
            action_sha1s: The actions to submit.

        Returns:
            The list of actions that have been submitted.
        """
        current_capacity = self.parallelism - len(self._actions_running)

        actions_to_run = []

        for _ in range(0, current_capacity):
            if len(action_sha1s) == 0:
                break

            action_to_run = action_sha1s.pop()
            actions_to_run.append(action_to_run)
            executor.submit(self.execute, action_to_run)

        return actions_to_run

    def _on_action_execution_start(self, action_sha1: ActionSha1) -> None:
        """Callback function to be called when an action execution is started.

        Args:
            action_sha1: The SHA-1 of the action that has been started.
        """
        with self._lock:
            # Add action to the set of running actions.
            self._actions_running.add(action_sha1)

            # Record action execution start in linearizable history.
            self._action_execution_start_history.append(action_sha1)

            self._log_current_status()

    def _on_action_execution_done(
        self, action_sha1: ActionSha1, action_output: Any
    ) -> None:
        """Callback function to be called when an action execution is done.

        Args:
            action_sha1: The SHA-1 of the action that has been executed.
        """
        with self._lock:
            # Record action execution end in linearizable history.
            self._action_execution_end_history.append(action_sha1)

            # Cache the result of the action.
            self._action_cache[action_sha1] = action_output

            # Remove the action from the set of running actions.
            self._actions_running.discard(action_sha1)

            # Decrement the pending dependencies count for all dependents of the action.
            for dependent in self.actions_info.action_dependents[action_sha1]:
                self._action_pending_dependencies_count[dependent] -= 1

            self._log_current_status()

    def _reinsert_critical_path_tail(self, critical_path: CriticalPath) -> None:
        """Removes the action at the head of the critical path (and its duration).

        Args:
            critical_path: The critical path whose first action's execution
            should be acknowledged.
        """
        duration, path = critical_path

        # If the executed action is the last action in the path, then there is
        # no need to re-add the path's tail to the critical paths.
        if len(path) == 1:
            return

        action_executed = path[0]

        self._critical_paths.push(
            (
                duration - self.actions_info.actions_by_sha1[action_executed].duration,
                path[1:],
            )
        )

    def _log_current_status(self) -> None:
        """Logs the currently running and currently done actions."""
        actions_running_prefix = ": " if self._actions_running else ""
        actions_done_prefix = (
            " | actions done: " if self._action_execution_end_history else ""
        )
        log.info(
            "%s actions running%s%s",
            len(self._actions_running),
            f"{actions_running_prefix}{", ".join(self._actions_running)}",
            f"{actions_done_prefix}{", ".join(self._action_execution_end_history)}",
        )
