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

from indication_native import _inside, load_source
from turn_marking import _segment_distance, native_route_plan


OFFSETS_M = (2.0, 4.0, 6.0)
PLACEMENT_SHIFTS_M = (0.0, 0.75, 1.5)


def construct_placement(source_path, source_sha256, form, shift_m):
    """Derive an exact in-intersection prop source from a checked original.

    A shift is construction variation. The parent authority claim is retained
    verbatim and remains unverified; no image visibility is inferred.
    """
    if isinstance(shift_m, bool) or shift_m not in PLACEMENT_SHIFTS_M:
        raise ValueError("Placement shift is not on the frozen physical grid")
    original = load_source(source_path, source_sha256, form)
    derived = json.loads(json.dumps(original))
    polygon = derived["intersection_polygon_xy_m"]
    for item in derived["indications"]:
        item["x"] += shift_m
        if not _inside([item["x"], item["y"]], polygon):
            raise ValueError("Shifted indication leaves sourced intersection")
    derived["parent_source_sha256"] = source_sha256
    derived["placement_shift_m"] = shift_m
    encoded = (json.dumps(derived, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return {
        "original_source_sha256": source_sha256,
        "derived_source_sha256": hashlib.sha256(encoded).hexdigest(),
        "derived_source_text": encoded.decode(),
        "placement_shift_setpoint_m": shift_m,
        "physical_xy_m": [[item["x"], item["y"]] for item in derived["indications"]],
        "authority_verified": False,
        "visible_pixels_verified": False,
    }


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
        placements = [construct_placement(source, source_sha256, "marker", value)
                      for value in PLACEMENT_SHIFTS_M]
        if len({row["derived_source_sha256"] for row in placements}) != 3:
            raise ValueError("Frozen placement sweep has duplicate sources")
        for row in placements:
            derived_path = Path(temp) / "derived.json"
            derived_path.write_text(row["derived_source_text"])
            reread = load_source(derived_path, row["derived_source_sha256"], "marker")
            if reread["indicated_course_xy_m"] != json.loads(source_bytes)["indicated_course_xy_m"]:
                raise ValueError("Placement changed the indicated course")
        for invalid in (-0.75, 0.5, 3.0):
            try:
                construct_placement(source, source_sha256, "marker", invalid)
            except ValueError as error:
                if "frozen physical grid" not in str(error):
                    raise
            else:
                raise ValueError("Off-grid placement was accepted")
        edge = json.loads(source_bytes)
        edge["indications"][0]["x"] = 103.5
        edge_bytes = (json.dumps(edge, sort_keys=True, separators=(",", ":")) + "\n").encode()
        edge_path = Path(temp) / "edge.json"
        edge_path.write_bytes(edge_bytes)
        try:
            construct_placement(edge_path, hashlib.sha256(edge_bytes).hexdigest(),
                                "marker", PLACEMENT_SHIFTS_M[-1])
        except ValueError as error:
            if "leaves sourced intersection" not in str(error):
                raise
        else:
            raise ValueError("Out-of-intersection placement was accepted")
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
        try:
            construct_placement(source, source_sha256, "marker", PLACEMENT_SHIFTS_M[0])
        except ValueError as error:
            if "hash" not in str(error):
                raise
        else:
            raise ValueError("Changed placement parent source was accepted")
    print(json.dumps({"source_sha256": source_sha256,
                      "setpoints_m": list(OFFSETS_M),
                      "target_max_deviation_m": [r["target_max_center_deviation_m"] for r in rows],
                      "off_grid_rejected": True, "changed_source_rejected": True,
                      "placement_setpoints_m": list(PLACEMENT_SHIFTS_M),
                      "placement_xy_m": [r["physical_xy_m"] for r in placements],
                      "placement_sources_distinct": True,
                      "placement_off_grid_rejected": True,
                      "placement_parent_change_rejected": True,
                      "placement_outside_intersection_rejected": True,
                      "native_launched": False, "legal_obedience_judgment": None}))


if __name__ == "__main__":
    main()
