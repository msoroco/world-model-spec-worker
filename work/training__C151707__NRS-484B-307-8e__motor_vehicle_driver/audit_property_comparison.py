"""Independent CPU comparison of saved property route measurements.

This verifies source joins and isolation only. It cannot decide legal purpose,
physical property authority or whether a CARLA capture is accepted.
"""
from __future__ import annotations

import json
from pathlib import Path

from property_bypass_measure import ASSIGNMENT


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def audit(road: dict, property_route: dict) -> dict:
    require(road.get("assignment_id") == ASSIGNMENT and
            property_route.get("assignment_id") == ASSIGNMENT,
            "comparison assignment mismatch")
    require(road.get("source_kind") == property_route.get("source_kind") and
            road.get("source_kind") in {"native_saved_sample", "synthetic_native_sample"},
            "matching original saved Native or explicit synthetic source kinds required")
    for key in ("map_inventory_sha256", "purpose_declaration_sha256",
                "approach_lane_id", "property_id", "property_boundary_source_id",
                "intersecting_street_id", "declared_purpose", "declaration_source_id"):
        require(road.get(key) is not None and road[key] == property_route.get(key),
                "comparison fixed condition differs: " + key)
    require(road.get("frame_count") == property_route.get("frame_count") == 600 and
            road.get("duration_s") == property_route.get("duration_s") == 30,
            "comparison duration differs")
    require(road.get("frame_source_sha256") and property_route.get("frame_source_sha256") and
            road["frame_source_sha256"] != property_route["frame_source_sha256"],
            "comparison needs distinct original frame sources")
    require(road.get("first_property_frame") is None and
            road.get("property_then_intersecting_street") is False,
            "road-only control entered property")
    require(property_route.get("property_then_intersecting_street") is True and
            isinstance(property_route.get("first_property_frame"), int) and
            isinstance(property_route.get("first_intersecting_street_frame"), int) and
            property_route["first_property_frame"] < property_route["first_intersecting_street_frame"],
            "property route did not enter intersecting street after property")
    require(property_route.get("steady_red_alone_before_property_entry") is True and
            property_route.get("steady_red_alone_at_property_entry") is True and
            property_route.get("cross_street_not_red_at_entry") is True,
            "property-route signal observations missing")
    require(road.get("legal_result") is None and property_route.get("legal_result") is None,
            "fixture cannot assert legal result")
    return {"format": "c151707-property-route-comparison-audit-v1",
            "assignment_id": ASSIGNMENT,
            "road_frame_source_sha256": road["frame_source_sha256"],
            "property_frame_source_sha256": property_route["frame_source_sha256"],
            "map_inventory_sha256": road["map_inventory_sha256"],
            "purpose_declaration_sha256": road["purpose_declaration_sha256"],
            "isolation_passed": True,
            "scope": "synthetic CPU diagnostic" if road["source_kind"] == "synthetic_native_sample"
                     else "original saved Native source comparison",
            "physical_acceptance": None, "legal_result": None}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--road", required=True)
    parser.add_argument("--property-route", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(Path(args.road).read_text()),
                           json.loads(Path(args.property_route).read_text())), sort_keys=True))
