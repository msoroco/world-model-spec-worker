"""Build explicit synthetic-only diagnostic recipes for exact driveway cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PLAN = json.loads((HERE / "case-plan.json").read_text())
EXAMPLE = json.loads((REPO / "runtime/fixtures/example.json").read_text())
X = [-11, -6, -3, 0, 1, 2, 4, 6, 8]


def text(value):
    return json.dumps(value, separators=(",", ":")) + "\n"


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for case in PLAN["cases"]:
    name = case["case_id"].split("__")[-1]
    spec = json.loads(json.dumps(EXAMPLE))
    files = spec["files"]
    rows = [json.loads(row) for row in files["video_frames.jsonl"].splitlines()]
    trace = [json.loads(row) for row in files["trace.jsonl"].splitlines()]
    provenance = json.loads(files["fixture-provenance.json"])
    provenance.update(diagnostic_fixture=True, physical_acceptance_claimed=False,
                      source_kind="synthetic_fixture", exact_case_id=case["case_id"])
    files["fixture-provenance.json"] = text(provenance)
    geometry = {
        "case_id": case["case_id"], "source_kind": "synthetic_fixture",
        "map_sha256": hashlib.sha256(files["road.xodr"].encode()).hexdigest(),
        "district_source": "authored synthetic residence-district context; original review pending",
        "frontage_source": "authored synthetic frontage context; original review pending",
        "private_driveway_source": "authored synthetic private-use context; original review pending",
        "sidewalk_source": "authored synthetic sidewalk polygon; original survey pending",
        "roadway_source": "authored synthetic connected road polygon; original survey pending",
        "connection_source": "authored synthetic route; original connection pending",
        "ego_vehicle_id": "diagnostic-ego",
        "district": "residence", "business_district": False,
        "access": "private_driveway", "road_connection": True,
        "crosswalk_assumed": False, "controlled_access_assumed": False,
        "driveway_polygon_m": [[-12, -3], [-1, -3], [-1, 3], [-12, 3]],
        "sidewalk_polygon_m": [[-2, -3], [2, -3], [2, 3], [-2, 3]],
        "roadway_polygon_m": [[3, -7], [13, -7], [13, 7], [3, 7]],
        "ego_route_xy_m": [[-11, 0], [-6, 0], [-3, 0], [0, 0], [1, 0], [2, 0], [4, 0], [6, 0], [8, 0]],
        "pedestrian_route_xy_m": [[0, -2], [0, 2]],
        "roadway_approaches": {
            "left": {"lane_source": "synthetic left lane", "route_xy_m": [[4, -6], [4, 0]]},
            "right": {"lane_source": "synthetic right lane", "route_xy_m": [[8, 6], [8, 0]]},
        },
    }
    activity = []
    for i, frame in enumerate(rows):
        ped = None
        if case["world_setup"]["pedestrian"] != "pedestrian_absent":
            intrude = case["world_setup"]["pedestrian"].endswith("_intrude")
            ped = {"actor_id": "diagnostic-pedestrian", "source": "synthetic fixture",
                   "xy_m": [0, -1.5 + i * .5 if intrude else -2 + i * .5],
                   "speed_mps": 1.0}
        road = None
        mode = case["world_setup"]["roadway_vehicle"]
        if mode != "roadway_clear":
            direction = "left" if mode.startswith("left_") else "right"
            intrude = mode.endswith("_intrude")
            road = {"actor_id": "diagnostic-roadway-vehicle", "source": "synthetic fixture",
                    "approach_direction": direction,
                    "xy_m": [4, -5 + i * .5] if direction == "left" and intrude else
                            [4, -6 + i * .5] if direction == "left" else
                            [8, 5 - i * .5] if intrude else [8, 6 - i * .5],
                    "speed_mps": 3.0}
        activity.append({"frame": frame["carla_frame"], "time_s": frame["time_s"],
                         "ego": {"actor_id": "diagnostic-ego", "source": "synthetic fixture",
                                 "xy_m": [X[i], 0],
                                 "speed_mps": 0.0 if i == 2 and name != "sidewalk_roll" else 2.0},
                         "pedestrian": ped, "roadway_vehicle": road})
    originals = {
        "frame_map": {"frames": [{"video_frame": i, "frame": frame["carla_frame"],
                                   "time_s": frame["time_s"]} for i, frame in enumerate(rows)]},
        "driveway_geometry": geometry,
        "activity": {"case_id": case["case_id"], "source_kind": "synthetic_fixture",
                     "samples": activity},
    }
    inventory = {"case_id": case["case_id"], "source_kind": "synthetic_fixture",
                 "diagnostic_fixture": True, "physical_acceptance_claimed": False,
                 "map_sha256": geometry["map_sha256"], "sources": {}, "media": {}}
    for key, value in originals.items():
        rel = "original-attempt/" + key + ".json"
        files[rel] = text(value)
        inventory["sources"][key] = {"path": key + ".json",
                                     "sha256": hashlib.sha256(files[rel].encode()).hexdigest()}
    files["original-attempt/inventory.json"] = text(inventory)
    capture_manifest = json.loads(files["capture/manifest.json"])
    capture_manifest["case_id"] = case["case_id"]
    capture_manifest["sources"]["trace.jsonl"] = hashlib.sha256(files["trace.jsonl"].encode()).hexdigest()
    files["capture/manifest.json"] = text(capture_manifest)
    source_path = HERE / ("diagnostic-" + name + ".json")
    source_path.write_text(json.dumps(spec, separators=(",", ":")) + "\n")
    source_ref = str(source_path.relative_to(REPO))
    recipe = {"format": "worker-fixture-recipe",
              "generator": {"source": source_ref, "sha256": sha(source_path)},
              "sources": [{"path": "diagnostic-input.json", "source": source_ref,
                           "sha256": sha(source_path)}]}
    write(HERE / ("diagnostic-" + name + "-recipe.json"), recipe)
    contract = {"format": "worker-measurement-contract", "case_id": case["case_id"],
                "negative": {"remove": ["original-attempt/activity.json"],
                             "error_contains": "Missing required source: original-attempt/activity.json"},
                "requirements": []}
    keys = ("district_driveway_context", "sidewalk_stop_evidence",
            "pedestrian_precedence_evidence", "roadway_approach_evidence")
    methods = ("measure_context", "measure_sidewalk_stop", "measure_pedestrian", "measure_roadway")
    for i, disposition in enumerate(PLAN["requirement_dispositions"]):
        contract["requirements"].append({
            "disposition_index": i, "requirement": disposition["requirement"],
            "source": disposition["source"], "output_key": keys[i],
            "kind": "sourced_context" if i == 0 else "measured",
            "method": methods[i], "value_type": "object",
            "inputs": ["original-attempt/driveway_geometry.json",
                       "original-attempt/activity.json"],
        })
    write(HERE / ("measurement-" + name + ".json"), contract)
