from collections import defaultdict
from typing import Dict, List, Set

from pydantic import BaseModel, PrivateAttr

from org_fraggles.build_action_scheduler.types import Action, Sha1


class ActionsInfo(BaseModel):
    # The list of actions.
    actions: List[Action]

    _actions_by_sha1: Dict[Sha1, Action] | None = PrivateAttr(default=None)

    _actions_dependents: Dict[Sha1, Set[Sha1]] | None = PrivateAttr(default=None)

    @property
    def actions_by_sha1(self) -> Dict[Sha1, Action]:
        """Returns a mapping of SHA-1 strings to action objects."""
        if self._actions_by_sha1 is None:
            self._actions_by_sha1 = {action.sha1: action for action in self.actions}

        return self._actions_by_sha1

    @property
    def action_dependents(self) -> Dict[Sha1, Set[Sha1]]:
        """Returns an inverse mapping of dependencies to dependents.

        E.g., if both 'B' and 'C' depend on 'A', then {'A': {'B', 'C'}}
        """
        if self._actions_dependents is None:
            action_dependents = defaultdict(set)

            for action in self.actions:
                for dep in action.dependencies:
                    if dep not in action_dependents:
                        action_dependents[dep] = set()
                    action_dependents[dep].add(action.sha1)

            self._actions_dependents = action_dependents

        return self._actions_dependents
