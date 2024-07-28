from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Sequence, Tuple

from org_fraggles.build_action_scheduler.types import Action, ActionDuration, Sha1

ExecutionBatch = List[Action]
BuildPlan = List[ExecutionBatch]


@dataclass
class BuildReport:
    """The representation of a build report."""

    execution_batches: List[ExecutionBatch]
    critical_path: List[Sha1]
    critical_path_duration: ActionDuration


def schedule(parallelism: int, actions: List[Action]) -> BuildReport:
    """Schedules actions with respect to their dependencies and parallelism.

    Args:
        parallelism: The maximum number of actions to execute in parallel.
        actions: The list of actions to schedule.

    Returns:
        A build plan with actions organized as sequential execution batches.
    """
    # Mapping of SHA-1 strings to action objects.
    actions_by_sha1: Dict[Sha1, Action] = {action.sha1: action for action in actions}

    # The original dependencies of each action. Will be used to restore the
    # original state of the actions at the end of the algorithm.
    original_action_dependencies: Dict[Sha1, List[Sha1]] = {
        action.sha1: action.dependencies for action in actions
    }

    # The number of an actions' dependencies that haven't been executed yet.
    action_pending_dependencies_count: Dict[Sha1, int] = {
        action.sha1: 0 for action in actions
    }

    # An inverse mapping of dependencies to dependents.
    #
    # E.g., if both "B" and "C" depend on "A", then {"A": ["B", "C"]}
    action_dependents: Dict[Sha1, Sequence[Sha1]] = defaultdict(list)

    # A mapping of action SHA-1 identifier to a tuple that represents an action
    # path that ends in that identifier.
    #
    # E.g., if:
    # - "A" depends on "B"
    # - "B" depends on "C"
    # - "C" depends on nothing
    #
    # Then:
    # {
    #   "C": (c_duration, ["C"]),
    #   "B": (b_duration, ["C", "B"]),
    #   "A": (a_duration, ["C", "B", "A"]),
    # }
    max_action_path_durations: Dict[Sha1, Tuple[ActionDuration, ActionPath]] = {
        action.sha1: (action.duration, [action.sha1]) for action in actions
    }

    # Initialize `action_dependents` and `action_pending_dependencies_count`.
    for action in actions:
        for dep in action.dependencies:
            action_dependents[dep].append(action.sha1)
            action_pending_dependencies_count[action.sha1] += 1

    leaf_action_sha1s = [
        action.sha1
        for action in actions
        if action_pending_dependencies_count[action.sha1] == 0
    ]

    if len(leaf_action_sha1s) == 0:
        raise ValueError("No initial actions without dependencies")

    queue = deque(leaf_action_sha1s)
    build_plan: BuildPlan = []

    # Iterate:
    # 1. Collect batch of actions with no dependencies of size up to `parallelism`.
    # 2. Execute the batch.
    while queue:
        # 1. Collect batch.
        current_batch = []

        for _ in range(parallelism):
            if not queue:
                break

            action = queue.popleft()
            current_batch.append(action)

        # 2. Execute batch.
        execute(
            actions_by_sha1,
            max_action_path_durations,
            action_dependents,
            action_pending_dependencies_count,
            queue,
            current_batch,
        )

        # 3. Get critical path.
        critical_path_duration, critical_path = max(
            max_action_path_durations.values(), key=lambda x: x[0]
        )

        # 4. Record batch execution in build plan.
        build_plan.append([actions_by_sha1[sha1] for sha1 in current_batch])

    # Restore original action dependencies that were consumed in the algorithm.
    for execution_batch in build_plan:
        for action in execution_batch:
            action.dependencies = original_action_dependencies[action.sha1]

    return BuildReport(
        execution_batches=build_plan,
        critical_path=critical_path,
        critical_path_duration=critical_path_duration,
    )


def execute(
    actions_by_sha1: Dict[Sha1, Action],
    max_action_path_durations: Dict[Sha1, Tuple[ActionDuration, ActionPath]],
    action_dependents: Dict[Sha1, Sequence[Sha1]],
    action_pending_dependencies_count: Dict[Sha1, int],
    queue: Deque[Sha1],
    batch: Sequence[Sha1],
) -> None:
    """Executes a batch of actions.

    Updates the state of `max_action_path_durations`, `action_pending_dependencies_count`, and `queue`.

    Args:
        actions_by_sha1: Mapping from SHA-1 strings to action objects.
        max_action_path_durations: Mapping from action to its duration and path.
        action_dependents: Mapping from action to its dependents.
        action_pending_dependencies_count: Count of pending dependencies for each action.
        queue: Queue of actions ready to be executed.
        batch: The current batch of actions to execute.

    Returns: the maximum
    """
    for action_sha1 in batch:
        current_duration, current_path = max_action_path_durations[action_sha1]

        for child in action_dependents[action_sha1]:
            new_duration = current_duration + actions_by_sha1[child].duration
            if new_duration > max_action_path_durations[child][0]:
                max_action_path_durations[child] = (
                    new_duration,
                    current_path + [child],
                )

            action_pending_dependencies_count[child] -= 1

            if action_pending_dependencies_count[child] == 0:
                queue.append(child)
