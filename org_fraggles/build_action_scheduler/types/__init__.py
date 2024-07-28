from dataclasses import dataclass
from typing import List

from pydantic import BaseModel, Field

Sha1 = str
ActionDuration = int
ActionPath = List[Sha1]


@dataclass
class Action:
    """The representation of a build action."""

    sha1: Sha1
    duration: ActionDuration
    dependencies: List[Sha1]


class ActionModel(BaseModel):
    """Pydantic model for a build action.

    Used for validation."""

    sha1: Sha1 = Field(..., min_length=1)
    duration: ActionDuration = Field(..., gt=0)
    dependencies: List[Sha1] = []
