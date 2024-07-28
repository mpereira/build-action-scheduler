import sys

import pytest

from org_fraggles.build_action_scheduler.cycle_detector import CycleDetector
from org_fraggles.build_action_scheduler.types import Action


def test_no_cycle():
    actions = [
        Action(sha1="a", duration=10, dependencies=[]),
        Action(sha1="b", duration=20, dependencies=["a"]),
        Action(sha1="c", duration=30, dependencies=["b"]),
        Action(sha1="d", duration=40, dependencies=["c"]),
    ]
    actions_by_sha1 = {action.sha1: action for action in actions}
    cycle_detector = CycleDetector(actions_by_sha1)
    assert not cycle_detector.detect_cycle()


def test_single_cycle():
    actions = [
        Action(sha1="a", duration=10, dependencies=["b"]),
        Action(sha1="b", duration=20, dependencies=["c"]),
        Action(sha1="c", duration=30, dependencies=["a"]),
    ]
    actions_by_sha1 = {action.sha1: action for action in actions}
    cycle_detector = CycleDetector(actions_by_sha1)
    assert cycle_detector.detect_cycle()


def test_multiple_cycles():
    actions = [
        Action(sha1="a", duration=10, dependencies=["b"]),
        Action(sha1="b", duration=20, dependencies=["c"]),
        Action(sha1="c", duration=30, dependencies=["a"]),
        Action(sha1="d", duration=40, dependencies=["e"]),
        Action(sha1="e", duration=50, dependencies=["f"]),
        Action(sha1="f", duration=60, dependencies=["d"]),
    ]
    actions_by_sha1 = {action.sha1: action for action in actions}
    cycle_detector = CycleDetector(actions_by_sha1)
    assert cycle_detector.detect_cycle()


def test_larger_graph_with_cycle():
    actions = [
        Action(sha1="a", duration=10, dependencies=["b", "c"]),
        Action(sha1="b", duration=20, dependencies=["d"]),
        Action(sha1="c", duration=30, dependencies=["d"]),
        Action(sha1="d", duration=40, dependencies=["e"]),
        Action(sha1="e", duration=50, dependencies=["b"]),  # Cycle here.
        Action(sha1="f", duration=60, dependencies=[]),
    ]
    actions_by_sha1 = {action.sha1: action for action in actions}
    cycle_detector = CycleDetector(actions_by_sha1)
    assert cycle_detector.detect_cycle()


def test_larger_graph_without_cycle():
    actions = [
        Action(sha1="a", duration=10, dependencies=["b", "c"]),
        Action(sha1="b", duration=20, dependencies=["d"]),
        Action(sha1="c", duration=30, dependencies=["d"]),
        Action(sha1="d", duration=40, dependencies=["e"]),
        Action(sha1="e", duration=50, dependencies=[]),
        Action(sha1="f", duration=60, dependencies=[]),
    ]
    actions_by_sha1 = {action.sha1: action for action in actions}
    cycle_detector = CycleDetector(actions_by_sha1)
    assert not cycle_detector.detect_cycle()


if __name__ == "__main__":
    sys.exit(pytest.main(sys.argv[1:]))
