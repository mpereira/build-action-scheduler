from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Deque, Dict, Set

from pydantic import BaseModel, PrivateAttr

from org_fraggles.build_action_scheduler.actions_info import ActionsInfo
from org_fraggles.build_action_scheduler.types import Action, Sha1


class ActionExecutor(BaseModel):
    """Execute actions."""

    # Actions info.
    actions_info: ActionsInfo

    # The maximum number of actions to be executing in parallel at any given time.
    parallelism: int

    # Actions that are running at a certain time.
    _actions_running: Set[Sha1] = PrivateAttr()

    # Thread pool executor for managing action execution
    _executor: ThreadPoolExecutor = PrivateAttr()

    _lock: Lock = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)
        self._executor = ThreadPoolExecutor(max_workers=self.parallelism)
        self._executor.submit

    def submit_as_many_as_possible(self, action_sha1s: Deque[Sha1]) -> int:
        return len(action_sha1s)

    def execute(self, action: Action) -> None:
        """Executes the given action.

        Args:
            action (Action): The action to execute.
        """
        print("executing action")
        print(action)
