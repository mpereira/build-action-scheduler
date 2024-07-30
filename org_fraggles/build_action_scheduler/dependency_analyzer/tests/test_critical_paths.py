import sys

import pytest

from org_fraggles.build_action_scheduler.actions_info import ActionsInfo
from org_fraggles.build_action_scheduler.dependency_analyzer import (
    CriticalPaths,
    DependencyAnalyzer,
    DependencyCycleError,
)
from org_fraggles.build_action_scheduler.types import Action


def test_critical_paths_no_dependencies():
    actions = [
        Action(sha1="a", duration=10, dependencies=[]),
        Action(sha1="b", duration=20, dependencies=[]),
        Action(sha1="c", duration=30, dependencies=[]),
    ]
    actions_info = ActionsInfo(actions=actions)
    dependency_analyzer = DependencyAnalyzer(actions_info=actions_info)
    critical_paths = dependency_analyzer.critical_paths()

    assert not critical_paths.empty()

    paths = []
    while not critical_paths.empty():
        paths.append(critical_paths.pop())

    expected_paths = [
        (10, ["a"]),
        (20, ["b"]),
        (30, ["c"]),
    ]

    assert sorted(paths) == sorted(expected_paths)


def test_critical_paths_with_dependencies():
    actions = [
        Action(sha1="a", duration=10, dependencies=[]),
        Action(sha1="b", duration=20, dependencies=["a"]),
        Action(sha1="c", duration=30, dependencies=["b"]),
        Action(sha1="d", duration=40, dependencies=["b"]),
        Action(sha1="e", duration=50, dependencies=["c", "d"]),
    ]
    actions_info = ActionsInfo(actions=actions)
    dependency_analyzer = DependencyAnalyzer(actions_info=actions_info)
    critical_paths = dependency_analyzer.critical_paths()

    assert not critical_paths.empty()

    paths = []
    while not critical_paths.empty():
        paths.append(critical_paths.pop())

    expected_paths = [
        (110, ["a", "b", "c", "e"]),
        (120, ["a", "b", "d", "e"]),
    ]

    assert sorted(paths) == sorted(expected_paths)


def test_critical_paths_with_cycle():
    actions = [
        Action(sha1="a", duration=10, dependencies=[]),
        Action(sha1="b", duration=20, dependencies=["a"]),
        Action(sha1="c", duration=30, dependencies=["b"]),
        Action(sha1="d", duration=40, dependencies=["c"]),
        Action(sha1="a", duration=50, dependencies=["d"]),  # Cycle here.
    ]
    actions_info = ActionsInfo(actions=actions)
    dependency_analyzer = DependencyAnalyzer(actions_info=actions_info)

    with pytest.raises(DependencyCycleError):
        dependency_analyzer.critical_paths()


if __name__ == "__main__":
    sys.exit(pytest.main(sys.argv[1:]))
