import json
from collections import defaultdict
from dataclasses import asdict
from typing import Dict, Set

import typer

from org_fraggles.build_action_scheduler.actions_info import ActionsInfo
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

    actions = [Action(**action.dict()) for action in action_models]

    actions_info = ActionsInfo(actions=actions)

    action_executor = ActionExecutor(
        parallelism=parallelism,
        actions_info=actions_info,
    )

    dependency_analyzer = DependencyAnalyzer(actions_info=actions_info)

    build_report = ActionScheduler(
        parallelism=parallelism,
        actions_info=actions_info,
        action_executor=action_executor,
        dependency_analyzer=dependency_analyzer,
    ).schedule()

    print(json.dumps(build_report, indent=2))


if __name__ == "__main__":
    typer.run(main)
