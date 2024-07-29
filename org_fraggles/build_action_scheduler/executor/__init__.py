from concurrent.futures import ThreadPoolExecutor
from typing import Dict

from pydantic import BaseModel, PrivateAttr

from org_fraggles.build_action_scheduler.types import Action, Sha1


class ActionExecutor(BaseModel):
    """A placeholder class for executing actions."""

    # Mapping of SHA-1 strings to action objects.
    actions_by_sha1: Dict[Sha1, Action]

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
