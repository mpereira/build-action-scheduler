import pytest

from org_fraggles.build_action_scheduler.actions_info import ActionsInfo
from org_fraggles.build_action_scheduler.dependency_analyzer import DependencyAnalyzer
from org_fraggles.build_action_scheduler.scheduler import ActionScheduler
from org_fraggles.build_action_scheduler.types import Action


@pytest.fixture
def actions_info():
    actions = [
        Action(sha1="a", duration=3, dependencies=["b", "e"]),
        Action(sha1="b", duration=2, dependencies=["c"]),
        Action(sha1="c", duration=1, dependencies=[]),
        Action(sha1="e", duration=5, dependencies=[]),
    ]
    return ActionsInfo(actions=actions)


@pytest.fixture
def dependency_analyzer(actions_info):
    return DependencyAnalyzer(actions_info=actions_info)


@pytest.fixture
def action_scheduler(actions_info, dependency_analyzer):
    return ActionScheduler(
        parallelism=2,
        action_status_polling_interval_s=1,
        actions_info=actions_info,
        dependency_analyzer=dependency_analyzer,
    )


def test_schedule_simple(action_scheduler):
    result = action_scheduler.schedule()
    assert "error" not in result
    assert "action_execution_history" in result
    assert "critical_path" in result
    assert result["critical_path"]["duration"] == 8
    assert result["critical_path"]["path"] == ["e", "a"]


if __name__ == "__main__":
    pytest.main()
