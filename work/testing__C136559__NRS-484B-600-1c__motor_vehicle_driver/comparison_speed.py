"""Independent source-bound comparison of posted-speed exact cases.

This checks physical measurement isolation, not statutory applicability.
"""
from __future__ import annotations

import json
from pathlib import Path

from speed_source_review import ASSIGNMENT, measure


ALTERNATIVES = {"below", "equal", "outside_zone", "opposite_direction",
                "non_authority_sign", "metric_equivalent", "sign_not_in_view"}
CONTROL_FIXED = ("highway_dedication_source", "public_access_source",
                 "narrow_road_geometry_source", "vehicle_clearance_source",
                 "governed_segment_source", "governed_direction_source",
                 "sign_position_source", "governed_road_id", "governed_segment_id",
                 "governed_direction", "vehicle_id")


def _packet(root, inventory, name):
    # measure() has already checked path confinement and source hashes.
    return json.loads((Path(root) / inventory["sources"][name]["path"]).read_text())


def audit_pair(base_root, base_inventory, other_root, other_inventory, alternative):
    """Require the named changed variable and every source-declared fixed field."""
    if alternative not in ALTERNATIVES:
        raise ValueError("unknown exact comparison alternative")
    base_case = ASSIGNMENT + "__above"
    other_case = ASSIGNMENT + "__" + alternative
    base = measure(Path(base_root), base_inventory, base_case)
    other = measure(Path(other_root), other_inventory, other_case)
    bc, oc = (_packet(root, inventory, "posted_control") for root, inventory in
              ((base_root, base_inventory), (other_root, other_inventory)))
    br, oroute = (_packet(root, inventory, "route_occupancy") for root, inventory in
                  ((base_root, base_inventory), (other_root, other_inventory)))
    if any(bc.get(key) != oc.get(key) for key in CONTROL_FIXED):
        raise ValueError("fixed posted control or roadway source changed")
    if (alternative != "non_authority_sign" and
            bc.get("posting_authority_source") != oc.get("posting_authority_source")):
        raise ValueError("fixed posting authority source changed")
    if base["original_frames"] != other["original_frames"] or base["original_frames"] < 900:
        raise ValueError("fixed original duration changed")
    if not base["public_authority_posted"] or base["governed_frames"] != base["original_frames"]:
        raise ValueError("baseline original governed portion missing")
    if not all(row["rate_difference_mps"] is not None and row["rate_difference_mps"] > 0
               for row in base["samples"]):
        raise ValueError("baseline speed not above posted rate throughout")
    b_rows, o_rows = br["samples"], oroute["samples"]
    if alternative not in ("below", "equal") and any(
            a["speed_mps"] != b["speed_mps"] for a, b in zip(base["samples"], other["samples"])):
        raise ValueError("fixed actual vehicle speed changed")
    def same_route(keys):
        return all(all(a.get(key) == b.get(key) for key in keys)
                   for a, b in zip(b_rows, o_rows))
    route_keys = ("road_id", "segment_id", "direction", "on_highway", "operating")
    if alternative in ("below", "equal"):
        if not same_route(route_keys) or bc != {**oc, "case_id": bc["case_id"]}:
            raise ValueError("strict-rate fixed route/control changed")
        expected = -1 if alternative == "below" else 0
        values = [row["rate_difference_mps"] for row in other["samples"]]
        if not values or not all((value < 0 if expected == -1 else value == 0) for value in values):
            raise ValueError("strict-rate alternative not measured")
    elif alternative == "outside_zone":
        if not same_route(("direction", "operating")) or other["governed_frames"] >= base["governed_frames"]:
            raise ValueError("posted portion difference not measured")
        if other["posted_rate_mps"] != base["posted_rate_mps"]:
            raise ValueError("fixed posted rate changed")
    elif alternative == "opposite_direction":
        if not same_route(("road_id", "segment_id", "on_highway", "operating")) or other["governed_frames"] != 0:
            raise ValueError("opposite-direction difference not measured")
        if {r["direction"] for r in o_rows} == {r["direction"] for r in b_rows}:
            raise ValueError("route direction did not change")
    elif alternative == "non_authority_sign":
        if not same_route(route_keys) or other["public_authority_posted"] or other["governed_frames"] != 0:
            raise ValueError("non-authority difference not measured")
    elif alternative == "metric_equivalent":
        if not same_route(route_keys) or bc["unit"] == oc["unit"] or abs(base["posted_rate_mps"] - other["posted_rate_mps"]) > 1e-6:
            raise ValueError("equivalent posted units not established")
    elif alternative == "sign_not_in_view":
        if not same_route(route_keys) or other["sign_in_camera_view"] or not base["sign_in_camera_view"] or not oc.get("off_camera_reading_assumption_source"):
            raise ValueError("source visibility difference not established")
    if alternative not in ("below", "equal", "outside_zone", "opposite_direction"):
        if base["posted_rate_mps"] != other["posted_rate_mps"] and alternative != "metric_equivalent":
            raise ValueError("fixed physical posted rate changed")
    return {"format": "c136559-source-comparison-v1", "baseline_case_id": base_case,
            "alternative_case_id": other_case, "alternative": alternative,
            "baseline_sources": base["source_sha256"],
            "alternative_sources": other["source_sha256"],
            "baseline_governed_frames": base["governed_frames"],
            "alternative_governed_frames": other["governed_frames"],
            "fixed_source_checks_passed": True,
            "legal_applicability": "unresolved"}
