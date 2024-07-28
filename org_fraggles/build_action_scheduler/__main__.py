import json
from collections import defaultdict
from dataclasses import asdict
from typing import Dict, Set

import typer

from org_fraggles.build_action_scheduler.dependency_analyzer import DependencyAnalyzer
from org_fraggles.build_action_scheduler.executor import ActionExecutor
from org_fraggles.build_action_scheduler.scheduler import ActionScheduler
from org_fraggles.build_action_scheduler.types import Action, ActionModel, Sha1


def main(
    parallelism: int = typer.Option(
        ..., help="The maximum number of actions to execute in parallel."
    ),
    actions_file: str = typer.Option(
        ...,
        help="The path to the JSON file containing the list of actions to schedule.",
    ),
) -> None:
    """Prints a JSON-formatted build report.

    Args:
        parallelism: The maximum number of actions to execute in parallel.
        actions_file: The path to the JSON file containing the list of actions to schedule.
    """
    with open(actions_file, "r") as f:
        actions_data = json.load(f)

    # Validate JSON data.
    action_models = [ActionModel(**action) for action in actions_data]

    # Get action objects.
    actions = [Action(**action.dict()) for action in action_models]

    actions_by_sha1: Dict[Sha1, Action] = {action.sha1: action for action in actions}

    action_dependents: Dict[Sha1, Set[Sha1]] = defaultdict(set)

    for action in actions:
        for dep in action.dependencies:
            if dep not in action_dependents:
                action_dependents[dep] = set()
            action_dependents[dep].add(action.sha1)

    action_executor = ActionExecutor(parallelism=parallelism)

    dependency_analyzer = DependencyAnalyzer(
        actions_by_sha1=actions_by_sha1,
        action_dependents=action_dependents,
    )

    # Schedule and print build.
    build_report = ActionScheduler(
        parallelism=parallelism,
        actions=actions,
        actions_by_sha1=actions_by_sha1,
        action_dependents=action_dependents,
        action_executor=action_executor,
        dependency_analyzer=dependency_analyzer,
    ).schedule()

    # execution_batches = [[asdict(a) for a in b] for b in build_report.execution_batches]
    # ordered_action_executions = [
    #     asdict(a) for b in build_report.execution_batches for a in b
    # ]

    # print(
    #     json.dumps(
    #         {
    #             "execution_batches": execution_batches,
    #             "ordered_action_executions": ordered_action_executions,
    #             "critical_path": build_report.critical_path,
    #             "critical_path_duration": build_report.critical_path_duration,
    #         },
    #         indent=2,
    #     )
    # )


if __name__ == "__main__":
    typer.run(main)
