from concurrent.futures import ThreadPoolExecutor
from typing import Dict

from pydantic import BaseModel, PrivateAttr

from org_fraggles.build_action_scheduler.actions_info import ActionsInfo
from org_fraggles.build_action_scheduler.types import Action, Sha1


class ActionExecutor(BaseModel):
    """Execute actions."""

    # Actions info.
    actions_info: ActionsInfo

    # Maximum number of actions to be executing in parallel at any given time.
    parallelism: int

    # Thread pool executor for managing action execution
    _executor: ThreadPoolExecutor = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)
        self._executor = ThreadPoolExecutor(max_workers=self.parallelism)
        self._executor.submit

    def execute(self, action: Action) -> None:
        """Executes the given action.

        Args:
            action (Action): The action to execute.
        """
        print("executing action")
        print(action)
