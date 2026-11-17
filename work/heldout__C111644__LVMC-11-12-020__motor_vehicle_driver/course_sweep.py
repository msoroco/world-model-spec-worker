"""Source-bound route targets for the turn-course deviation judgment sweep.

These are authored controller targets, not measured motion or a legal cutoff.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from math import hypot
from pathlib import Path
from tempfile import TemporaryDirectory

from indication_native import load_source
from turn_marking import _segment_distance, native_route_plan


OFFSETS_M = (2.0, 4.0, 6.0)


def construct(source_path, source_sha256, form, offset_m):
    """Build one exact target from a checked original indication source.

    Keep the approach and indicated course fixed. A right-side lateral target
    changes only the post-interior route; original body motion must later be
    measured against the unchanged indicated course.
    """
    if isinstance(offset_m, bool) or offset_m not in OFFSETS_M:
        raise ValueError("Departure offset is not on the frozen physical grid")
    source = load_source(source_path, source_sha256, form)
    plan = native_route_plan(source, "depart", departure_m=offset_m)
    route = plan["target_route_xy_m"]
    course = plan["course_xy_m"]
    if len(route) != len(course) or route[:2] != course[:2]:
        raise ValueError("Sweep changed the sourced approach")
    target_gap = max(
        min(_segment_distance(point, a, b) for a, b in zip(course, course[1:]))
        for point in route
    )
    if target_gap < 1.0 or hypot(route[-1][0] - course[-1][0], route[-1][1] - course[-1][1]) < offset_m - 1e-6:
        raise ValueError("Sweep target has no sourced route separation")
    return {
        **plan,
        "source_sha256": source_sha256,
        "course_deviation_setpoint_m": offset_m,
        "target_max_center_deviation_m": target_gap,
        "measured_original_max_center_deviation_m": None,
        "legal_obedience_judgment": None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-diagnostic", required=True)
    args = parser.parse_args()
    diagnostic = json.loads(Path(args.check_diagnostic).read_text())
    source_bytes = diagnostic["files"]["turn_indication_original.json"].encode()
    with TemporaryDirectory() as temp:
        source = Path(temp) / "turn_indication_original.json"
        source.write_bytes(source_bytes)
        source_sha256 = hashlib.sha256(source_bytes).hexdigest()
        rows = [construct(source, source_sha256, "marker", value)
                for value in OFFSETS_M]
        if len({tuple(row["target_route_xy_m"][-1]) for row in rows}) != 3:
            raise ValueError("Frozen course sweep has duplicate route targets")
        try:
            construct(source, source_sha256, "marker", 3.0)
        except ValueError as error:
            if "frozen physical grid" not in str(error):
                raise
        else:
            raise ValueError("Off-grid course target was accepted")
        source.write_bytes(source_bytes + b" ")
        try:
            construct(source, source_sha256, "marker", OFFSETS_M[0])
        except ValueError as error:
            if "hash" not in str(error):
                raise
        else:
            raise ValueError("Changed indication source was accepted")
    print(json.dumps({"source_sha256": source_sha256,
                      "setpoints_m": list(OFFSETS_M),
                      "target_max_deviation_m": [r["target_max_center_deviation_m"] for r in rows],
                      "off_grid_rejected": True, "changed_source_rejected": True,
                      "native_launched": False, "legal_obedience_judgment": None}))


if __name__ == "__main__":
    main()
