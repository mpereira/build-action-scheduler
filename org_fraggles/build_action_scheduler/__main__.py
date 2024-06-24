import json
from dataclasses import asdict

import typer

from org_fraggles.build_action_scheduler import Action, ActionModel, schedule


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
    action_objects = [Action(**action.dict()) for action in action_models]

    # Schedule and print build.
    build_report = schedule(parallelism, action_objects)

    execution_batches = [[asdict(a) for a in b] for b in build_report.execution_batches]
    ordered_action_executions = [
        asdict(a) for b in build_report.execution_batches for a in b
    ]

    print(
        json.dumps(
            {
                "execution_batches": execution_batches,
                "ordered_action_executions": ordered_action_executions,
                "critical_path": build_report.critical_path,
                "critical_path_duration": build_report.critical_path_duration,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
