import logging
import time
from collections import defaultdict, deque
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import Any, Deque, Dict, List, Set, Tuple

from pydantic import BaseModel, PrivateAttr

from org_fraggles.build_action_scheduler.actions_info import ActionsInfo
from org_fraggles.build_action_scheduler.dependency_analyzer import (
    CriticalPath,
    CriticalPaths,
    DependencyAnalyzer,
    DependencyCycleError,
)
from org_fraggles.build_action_scheduler.executor import ActionExecutor
from org_fraggles.build_action_scheduler.types import Sha1

log = logging.getLogger(__name__)

Timestamp = str


class ActionScheduler(BaseModel):
    # The maximum number of actions to be executing in parallel at any given time.
    parallelism: int

    # TODO.
    action_status_polling_interval_s: int

    # Actions info.
    actions_info: ActionsInfo

    # The action executor.
    action_executor: ActionExecutor

    # The dependency analyzer.
    dependency_analyzer: DependencyAnalyzer

    # Priority queue to store paths and their overall durations.
    _critical_paths: CriticalPaths = PrivateAttr(default=None)

    # TODO.
    _action_pending_dependencies_count: Dict[Sha1, int] = PrivateAttr(
        default=defaultdict(int)
    )

    # TODO.
    _action_cache: Dict[Sha1, Any] = PrivateAttr(default_factory=dict)

    # Actions that are running at a certain time.
    _actions_running: Set[Sha1] = PrivateAttr(default_factory=set)

    # TODO.
    _action_execution_start_history: List[Sha1] = PrivateAttr(default_factory=list)

    # TODO.
    _action_execution_start_times: Dict[Sha1, Timestamp] = PrivateAttr(
        default_factory=dict
    )

    # TODO.
    _action_execution_end_times: Dict[Sha1, Timestamp] = PrivateAttr(
        default_factory=dict
    )

    # Thread pool executor for managing action execution
    _executor: ThreadPoolExecutor = PrivateAttr()

    _lock: Lock = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)

        # Set initial number of pending dependencies for each action.
        self._action_pending_dependencies_count = (
            self.actions_info.action_dependencies_count
        )

        self._lock = Lock()

    def prepare_next_ready_actions(self) -> List[Sha1]:
        ready_actions = []
        ready_actions_set = set()

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

        log.info(f"Ready actions: {ready_actions}")
        return ready_actions

    def schedule(self) -> Dict[str, Any]:
        """Schedules actions for execution."""
        ready_actions = deque([])

        try:
            self._critical_paths = self.dependency_analyzer.critical_paths()
        except DependencyCycleError:
            return {"error": "Dependency cycle detected"}

        overall_critical_path = self._critical_paths.peek()

        with ThreadPoolExecutor(max_workers=self.parallelism) as executor:
            while not self._critical_paths.empty():
                for action in self.prepare_next_ready_actions():
                    ready_actions.appendleft(action)

                actions_submitted = self._submit_as_many_as_possible(
                    executor, ready_actions
                )

                if len(actions_submitted) == 0:
                    actions_running_prefix = ": " if self._actions_running else ""
                    log.info(
                        "Sleeping for %ss (%s actions running%s)",
                        self.action_status_polling_interval_s,
                        len(self._actions_running),
                        f"{actions_running_prefix}{", ".join(self._actions_running)}",
                    )
                    time.sleep(self.action_status_polling_interval_s)

                    continue

        return {
            "action_execution_history": self._action_execution_start_history,
            "critical_path": {
                "duration": overall_critical_path[0],
                "path": overall_critical_path[1],
            },
        }

    def _submit_as_many_as_possible(
        self, executor: ThreadPoolExecutor, action_sha1s: Deque[Sha1]
    ) -> List[Sha1]:
        current_capacity = self.parallelism - len(self._actions_running)

        actions_to_run = []

        for _ in range(0, current_capacity):
            if len(action_sha1s) == 0:
                break

            action_to_run = action_sha1s.pop()
            actions_to_run.append(action_to_run)
            executor.submit(self.execute, action_to_run)

        return actions_to_run

    def execute(self, action_sha1: Sha1) -> int:
        """Executes the given action.

        Args:
            action (Action): The action to execute.
        """
        self._on_action_execution_start(action_sha1)

        duration = self.actions_info.actions_by_sha1[action_sha1].duration
        time.sleep(duration)

        self._on_action_execution_done(action_sha1, duration)

        return duration

    def _on_action_execution_start(self, action_sha1: Sha1) -> None:
        with self._lock:
            # Add action to the set of running actions.
            self._actions_running.add(action_sha1)

            # Record action execution in linearizable history.
            self._action_execution_start_history.append(action_sha1)

    def _on_action_execution_done(self, action_sha1: Sha1, action_output: Any) -> None:
        """Callback function to be called when an action execution is done.

        Args:
            action_sha1: The SHA-1 of the action that has been executed.
        """
        with self._lock:
            # Cache the result of the action.
            self._action_cache[action_sha1] = action_output

            # Remove the action from the set of running actions.
            self._actions_running.discard(action_sha1)

            # Decrement the pending dependencies count for all dependents of the action.
            for dependent in self.actions_info.action_dependents[action_sha1]:
                self._action_pending_dependencies_count[dependent] -= 1

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
