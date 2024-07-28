from collections import defaultdict
from typing import Dict, List, Set, Tuple

from pydantic import BaseModel, PrivateAttr

from org_fraggles.build_action_scheduler.dependency_analyzer import DependencyAnalyzer
from org_fraggles.build_action_scheduler.executor import ActionExecutor
from org_fraggles.build_action_scheduler.types import (
    Action,
    ActionDuration,
    ActionPath,
    Sha1,
)


class ActionScheduler(BaseModel):
    # The maximum number of actions to execute in parallel.
    parallelism: int

    # The actions to schedule and execute.
    actions: List[Action]

    # The actions to schedule and execute.
    action_executor: ActionExecutor

    dependency_analyzer: DependencyAnalyzer

    # Mapping of SHA-1 strings to action objects.
    actions_by_sha1: Dict[Sha1, Action]

    # The original dependencies of each action. Will be used to restore the
    # original state of the actions at the end of the algorithm.
    _original_action_dependencies: Dict[Sha1, List[Sha1]] = PrivateAttr(
        default_factory=dict
    )

    # The number of an actions' dependencies that haven't been executed yet.
    #
    # E.g., if:
    # - 'A' and 'C' have 2 pending dependencies
    # - 'B' has 1 pending dependency
    #
    # Then:
    # {
    #   'A': 2,
    #   'B': 1,
    #   'C': 2,
    # }
    _action_pending_dependencies_count: Dict[Sha1, int] = PrivateAttr(
        default_factory=lambda: defaultdict(int)
    )

    # Pending dependencies count mapped to actions.
    #
    # E.g., if:
    # - 'A' and 'C' have 2 pending dependencies
    # - 'B' has 1 pending dependency
    #
    # Then:
    # {
    #   1: {'B'},
    #   2: {'A', 'C'},
    # }
    _pending_dependencies_count_actions: Dict[int, Set[Sha1]] = PrivateAttr(
        default_factory=lambda: defaultdict(set)
    )

    # An inverse mapping of dependencies to dependents.
    #
    # E.g., if both 'B' and 'C' depend on 'A', then {'A': {'B', 'C'}}
    _action_dependents: Dict[Sha1, Set[Sha1]] = PrivateAttr(
        default_factory=lambda: defaultdict(set)
    )

    # A mapping of action SHA-1 identifier to a tuple that represents an action
    # path that ends in that identifier.
    #
    # E.g., if:
    # - 'A' depends on 'B'
    # - 'B' depends on 'C'
    # - 'C' depends on nothing
    #
    # Then:
    # {
    #   'C': (c_duration, ['C']),
    #   'B': (b_duration, ['C', 'B']),
    #   'A': (a_duration, ['C', 'B', 'A']),
    # }
    _max_action_path_durations: Dict[Sha1, Tuple[ActionDuration, ActionPath]] = (
        PrivateAttr(default_factory=dict)
    )

    def __init__(self, **data):
        super().__init__(**data)

        self._original_action_dependencies = {
            action.sha1: action.dependencies for action in self.actions
        }

        self._max_action_path_durations = {
            action.sha1: (action.duration, [action.sha1]) for action in self.actions
        }

        for action in self.actions:
            for dep in action.dependencies:
                if dep not in self._action_dependents:
                    self._action_dependents[dep] = set()
                self._action_dependents[dep].add(action.sha1)
                if action.sha1 not in self._action_pending_dependencies_count:
                    self._action_pending_dependencies_count[action.sha1] = 0
                self._action_pending_dependencies_count[action.sha1] += 1

                if (
                    self._action_pending_dependencies_count[action.sha1]
                    not in self._pending_dependencies_count_actions
                ):
                    self._pending_dependencies_count_actions[
                        self._action_pending_dependencies_count[action.sha1]
                    ] = set()

        for action in self.actions:
            self._pending_dependencies_count_actions[
                self._action_pending_dependencies_count[action.sha1]
            ].add(action.sha1)

        print(self.dependency_analyzer.critical_paths())

    def schedule(self) -> None:
        """Schedules the actions for execution."""
        print("self._action_dependents")
        print(self._action_dependents)
        print("self._action_pending_dependencies_count")
        print(self._action_pending_dependencies_count)
        print("self._pending_dependencies_count_actions")
        print(self._pending_dependencies_count_actions)
        print("self._max_action_path_durations")
        print(self._max_action_path_durations)

        # 1. schedule as many actions to be executed as possible based on
        # `parallelism` and `self._pending_dependencies_count_actions[0]`.

        # 2. as actions finish executing, update
        # `self._pending_dependencies_count_actions` and
        # `self._action_pending_dependencies_count`.

        # 3. repeat until there are no more actions to execute.
        # Actions are executed with `self.action_executor.execute(action)`.

        queue = []
        for action_sha1 in self._pending_dependencies_count_actions[0]:
            queue.append(action_sha1)

        while queue:
            current_batch = []
            for _ in range(self.parallelism):
                if not queue:
                    break
                current_batch.append(queue.pop())

            for action_sha1 in current_batch:
                self.action_executor.execute(self.actions_by_sha1[action_sha1])

            for action_sha1 in current_batch:
                for child in self._action_dependents[action_sha1]:
                    self._action_pending_dependencies_count[child] -= 1
                    if self._action_pending_dependencies_count[child] == 0:
                        queue.append(child)
