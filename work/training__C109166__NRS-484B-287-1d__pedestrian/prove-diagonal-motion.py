"""CPU check of exact walker requests, paired isolation, and camera plan."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native"))
from diagonal_motion import FRAMES, apply_walker_control, camera_plan, command, validate_pair


def main() -> None:
    def rows(display):
        return [dict(command(frame), device_display_request=display,
                     official_device_verified=False) for frame in range(FRAMES)]

    a = rows("diagonal_walk_requested")
    b = rows("no_diagonal_permission")
    report = validate_pair(a, b)
    assert [command(i)["walker_speed_mps"] > 0 for i in (99, 100, 339, 340)] == [False, True, True, False]
    assert command(100)["target_xy_m"] == (-6.0, -6.0)
    assert command(340)["target_xy_m"] == (6.0, 6.0)
    assert len({x["name"] for x in camera_plan()}) == 4
    class FakeCarla:
        @staticmethod
        def Vector3D(*xyz):
            return xyz

        @staticmethod
        def WalkerControl(direction, speed, jump):
            return (direction, speed, jump)

    class FakeWalker:
        def apply_control(self, value):
            self.last = value

    walker = FakeWalker()
    apply_walker_control(walker, FakeCarla, 150)
    assert walker.last[1] > 0 and walker.last[2] is False
    apply_walker_control(walker, FakeCarla, 400)
    assert walker.last[1] == 0
    b[201]["target_xy_m"] = (0.0, 0.0)
    try:
        validate_pair(a, b)
    except ValueError as error:
        assert "motion changed" in str(error)
    else:
        raise AssertionError("changed paired motion accepted")
    b = rows("no_diagonal_permission")
    b[201]["official_device_verified"] = True
    try:
        validate_pair(a, b)
    except ValueError as error:
        assert "authority overstated" in str(error)
    else:
        raise AssertionError("invented authority accepted")
    report.update(format="c109166-diagonal-motion-cpu-proof-v1", passed=True,
                  controller_sha256=hashlib.sha256((HERE / "native/diagonal_motion.py").read_bytes()).hexdigest(),
                  negative_probes=2, original_native_observed=False)
    target = HERE / "diagonal-motion-proof.json"
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
