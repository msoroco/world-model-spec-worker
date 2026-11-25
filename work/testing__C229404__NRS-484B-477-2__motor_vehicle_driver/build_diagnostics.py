"""Build nine-frame synthetic access fixtures for CPU compatibility only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent


def dump(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    base = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    mapping = [json.loads(line) for line in base["files"]["video_frames.jsonl"].splitlines() if line.strip()]
    if len(mapping) != 9:
        raise ValueError("generic Core/video smoke fixture changed")
    for case in plan["cases"]:
        slug = case["case_id"].removeprefix(plan["assignment_id"] + "__")
        diagnostic = json.loads(json.dumps(base))
        files = diagnostic["files"]
        source_root = "original-attempt/"
        kind = case["access_kind"]
        center_x = 1 if case["parking_position"] == "overlap" else 6
        frames = [{"frame": row["carla_frame"], "time_s": row["time_s"],
                   "video_frame": i} for i, row in enumerate(mapping)]
        geometry = {"case_id": case["case_id"],
                    "source_kind": "original_native_geometry",
                    "map_sha256": sha(files["road.xodr"]),
                    "highway_status": True, "cul_de_sac": False,
                    "highway_source": "synthetic-diagnostic:highway-stipulation",
                    "alley_classification_source": "synthetic-diagnostic:alley-stipulation",
                    "cul_de_sac_source": "synthetic-diagnostic:connected-ends-stipulation",
                    "start_connection_source": "synthetic-diagnostic:west-end",
                    "end_connection_source": "synthetic-diagnostic:east-end",
                    "property_abutting_source": "synthetic-diagnostic:parcel-stipulation",
                    "property_id": "diagnostic-parcel-1",
                    "driveway_ownership_source": "synthetic-diagnostic:owner-stipulation",
                    "vehicular_use_source": "synthetic-diagnostic:vehicle-entry-stipulation",
                    "ego_vehicle_id": "ego", "access_kind": kind,
                    "centerline_start_m": [-50, 2], "centerline_end_m": [100, 2],
                    "ego_length_m": 4.5, "ego_width_m": 1.8,
                    "access_corridor_polygon_m": [[0, 0], [4, 0], [4, 5], [0, 5]]}
        source_values = {
            "frame_map": {"frames": frames},
            "alley_geometry": geometry,
            "vehicle_footprint": {"case_id": case["case_id"],
                                  "source_kind": "original_native",
                                  "samples": [{"frame": row["frame"],
                                               "time_s": row["time_s"],
                                               "vehicle_id": "ego",
                                               "polygon_m": [[center_x, 1], [center_x + 2, 1],
                                                             [center_x + 2, 3], [center_x, 3]]}
                                              for row in frames]},
            "activity": {"case_id": case["case_id"],
                         "source_kind": "original_native",
                         "samples": [{"frame": row["frame"], "time_s": row["time_s"],
                                      "state": "parked" if i >= 3 else "approaching",
                                      "speed_mps": 0 if i >= 3 else 2}
                                     for i, row in enumerate(frames)]}}
        inventory = {"case_id": case["case_id"], "source_kind": "original_native",
                     "diagnostic_fixture": True, "map_sha256": geometry["map_sha256"],
                     "sources": {}, "media": {}}
        for name, value in source_values.items():
            content = dump(value)
            files[source_root + name + ".json"] = content
            inventory["sources"][name] = {"path": name + ".json",
                                           "sha256": sha(content)}
        files[source_root + "inventory.json"] = dump(inventory)
        files["fixture-provenance.json"] = dump({"diagnostic_fixture": True,
                                                 "physical_acceptance_claimed": False,
                                                 "scope": "nine-frame synthetic alley access and generic Core/video smoke test"})
        # These original-green exports are unrelated to the selected alley law.
        for name in ("original-events.json", "original-green-packet.json", "site.json"):
            files.pop(name, None)
        files.pop("acquisition.json", None)
        spec_path = ROOT / ("diagnostic-" + slug + ".json")
        spec_path.write_text(json.dumps(diagnostic, separators=(",", ":")) + "\n")
        reference = {"source": str(spec_path.relative_to(REPO)),
                     "sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest()}
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-input.json", **reference}],
                  "generator": reference}
        (ROOT / ("diagnostic-" + slug + "-recipe.json")).write_text(dump(recipe))
        contract = {"format": "worker-measurement-contract", "case_id": case["case_id"],
                    "requirements": [{"disposition_index": 0,
                                      "requirement": plan["requirement_dispositions"][0]["requirement"],
                                      "source": plan["requirement_dispositions"][0]["source"],
                                      "output_key": "access_position_measurement",
                                      "method": "measure_alley_access", "value_type": "object",
                                      "kind": "measured",
                                      "inputs": [source_root + name + ".json" for name in
                                                 ("frame_map", "alley_geometry",
                                                  "vehicle_footprint", "activity")] }],
                    "negative": {"remove": [source_root + "activity.json"],
                                 "error_contains": "Missing required source: original-attempt/activity.json"}}
        (ROOT / ("measurement-" + slug + ".json")).write_text(dump(contract))


if __name__ == "__main__":
    main()
