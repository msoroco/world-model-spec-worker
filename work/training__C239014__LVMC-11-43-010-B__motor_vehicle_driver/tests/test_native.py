"""CPU checks for authored ring and motion requests; no Native execution."""
import math

from geometry import check as geometry_check
from runner import CAMERAS, FRAMES, RATE, RELEASE, check, target


def test_geometry_and_capture_contract():
    assert geometry_check()["authored_topology_passed"]
    assert check()["native_executed"] is False
    assert FRAMES == RATE * 30
    assert len({camera[0] for camera in CAMERAS}) == 4


def test_comparison_changes_only_entry_release():
    assert RELEASE == {"condition_a": 17.0, "condition_b": 12.5}
    for t in (0, 12, 17, 24, 29.95):
        for role in ("lead", "follower"):
            assert target(role, t, RELEASE["condition_a"]) == target(
                role, t, RELEASE["condition_b"])
    for condition, release in RELEASE.items():
        assert target("ego", release - .05, release)[1] == 0
        assert math.isclose(target("ego", release, release)[1], 4.8)
