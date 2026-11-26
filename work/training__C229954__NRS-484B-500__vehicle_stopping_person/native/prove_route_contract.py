"""Source-shaped positive and missing-original-source route proofs."""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path

from route_contract import validate


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def make_source(folder):
    folder.mkdir()
    name, device_id = "SyntheticRoad", "synthetic-device"
    targets = {}
    for condition, x in (("condition_a", 10), ("condition_b", 18)):
        targets[condition] = {
            "location_xyz_m": [x, 0, 0],
            "vehicle_footprint_map_m": rect(x - 1, -0.8, x + 1, 0.8),
            "drivable_lane_source": "synthetic lane survey",
            "route_alignment_source": "synthetic waypoint survey",
            "person_caused_stop": True,
        }
    originals = {
        "device": {"map_name": name, "device_id": device_id,
                   "authority_status": "source_reviewed_official", "content": "no stopping",
                   "erected": True, "active_first_frame": 0, "active_last_frame": 599,
                   "authority_source": "synthetic authority", "content_source": "synthetic pixels"},
        "designation": {"map_name": name, "device_id": device_id,
                        "designation_source": "synthetic plan",
                        "designated_polygon_map_m": rect(8, -2, 12, 2)},
        "route": {"map_name": name, "device_id": device_id,
                  "fixed_context_id": "same synthetic road-device-traffic",
                  "approach_waypoints_xyz_m": [[0, 0, 0], [10, 0, 0]],
                  "person_caused_stop_source": "synthetic controller",
                  "traffic_and_direction_source": "synthetic context log",
                  "stop_targets": targets},
        "map": {"map_name": name, "hazard_context_source": "synthetic survey",
                "physical_hazard_or_congestion_facts": "synthetic roadway constriction"},
    }
    source = {"source_kind": "original_official_device_review", "map_name": name,
              "device_id": device_id, "sources": {}}
    for key, data in originals.items():
        path = folder / (key + ".json")
        path.write_text(json.dumps(data, sort_keys=True) + "\n")
        source["sources"][key] = {"path": str(path),
                                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return source


def reject(source, mutation, expected):
    altered = copy.deepcopy(source)
    mutation(altered)
    try:
        validate(altered, "condition_a")
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError((expected, str(error))) from error
        return str(error)
    raise AssertionError("A bad original source passed: " + expected)


def main():
    with tempfile.TemporaryDirectory(prefix="c229954-route-", dir=".runtime-work") as directory:
        source = make_source(Path(directory) / "sources")
        inside = validate(source, "condition_a")
        outside = validate(source, "condition_b")
        assert inside["overlap_fraction"] == 1.0
        assert outside["overlap_fraction"] == 0.0
        assert inside["fixed_context_id"] == outside["fixed_context_id"]
        negatives = {
            "missing_device": reject(source, lambda s: s["sources"].pop("device"), "device source reference"),
            "changed_designation": reject(source, lambda s: s["sources"]["designation"].__setitem__("sha256", "0" * 64), "changed designation source"),
            "missing_route": reject(source, lambda s: s["sources"].pop("route"), "route source reference"),
            "changed_map": reject(source, lambda s: s["sources"]["map"].__setitem__("sha256", "0" * 64), "changed map source"),
            "wrong_device": reject(source, lambda s: s.__setitem__("device_id", "other"), "device identity"),
        }
        print(json.dumps({"format": "worker-designated-route-synthetic-proof",
                          "condition_a": inside, "condition_b": outside,
                          "negative_rejections": negatives,
                          "synthetic_only": True, "physical_completion": False},
                         indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
