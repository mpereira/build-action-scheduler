import json
import logging
import time
from typing import Annotated

import typer

from org_fraggles.build_action_scheduler.actions_info import ActionsInfo
from org_fraggles.build_action_scheduler.dependency_analyzer import DependencyAnalyzer
from org_fraggles.build_action_scheduler.scheduler import ActionScheduler
from org_fraggles.build_action_scheduler.types import Action, ActionModel

log = logging.getLogger(__name__)

logging.Formatter.converter = time.gmtime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)


def main(
    parallelism: Annotated[
        int,
        typer.Option(..., help="The maximum number of actions to execute in parallel."),
    ],
    actions_file: Annotated[
        str,
        typer.Option(
            ...,
            help="The path to the JSON file containing the list of actions to schedule.",
        ),
    ],
    action_status_polling_interval_s: Annotated[
        int, typer.Option(..., help="TODO")
    ] = 1,
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

    dependency_analyzer = DependencyAnalyzer(actions_info=actions_info)

    build_report = ActionScheduler(
        parallelism=parallelism,
        action_status_polling_interval_s=action_status_polling_interval_s,
        actions_info=actions_info,
        dependency_analyzer=dependency_analyzer,
    ).schedule()

    print(json.dumps(build_report, indent=2))


if __name__ == "__main__":
    typer.run(main)
