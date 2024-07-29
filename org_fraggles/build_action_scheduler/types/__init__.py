from dataclasses import dataclass
from typing import List

from pydantic import BaseModel, Field

ActionSha1 = str
ActionDuration = int
ActionPath = List[ActionSha1]


@dataclass
class Action:
    """The representation of a build action."""

    sha1: ActionSha1
    duration: ActionDuration
    dependencies: List[ActionSha1]


class ActionModel(BaseModel):
    """Pydantic model for a build action.

    Used for validation."""

    sha1: ActionSha1 = Field(..., min_length=1)
    duration: ActionDuration = Field(..., gt=0)
    dependencies: List[ActionSha1] = []
