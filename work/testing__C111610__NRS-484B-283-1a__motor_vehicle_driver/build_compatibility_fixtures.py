"""Build labelled synthetic C111610 fixtures for CPU software compatibility.

The copied nine-frame adapter graph is diagnostic converter input only. The
case-specific crosswalk sources are separately inventoried and never claim an
original physical run.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / "work/testing__C108447__NRS-484B-307-8e__motor_vehicle_driver/diagnostics/ordinary_crossing/specification.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def text(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def site_packet(case):
    suffix = case.rsplit("__", 1)[-1]
    site = {
        "diagnostic_fixture": True, "source": "original_native_map",
        "map_name": "C111610 synthetic software fixture", "intersection_id": "diagnostic-intersection",
        "highway_context": {"source": "original_map_and_local_review", "classification": "diagnostic"},
        "crosswalk": {"source": "original_map_marking",
                      "polygon_xy_m": [[-2, -1], [4, -1], [4, 5], [-2, 5]]},
        "ego_turn": {"direction": "left", "connected": True,
                     "waypoints": [[-8, -4], [-2, -2], [0, 0], [0, 8]],
                     "destination_lane_ids": ["north_1", "north_2"]},
        "lanes": [
            {"lane_id": "north_1", "direction": "north", "type": "driving",
             "polygon_xy_m": [[-2, 0], [0, 0], [0, 9], [-2, 9]]},
            {"lane_id": "north_2", "direction": "north", "type": "driving",
             "polygon_xy_m": [[0, 0], [2, 0], [2, 9], [0, 9]]},
            {"lane_id": "south_1", "direction": "south", "type": "driving",
             "polygon_xy_m": [[2, 0], [4, 0], [4, 9], [2, 9]]}],
        "official_devices": {"inventory_source": "original_map_and_actor_scan",
                             "coverage": "all_relevant_approaches", "entries": []}}
    if suffix.endswith("nonoperating") or suffix.endswith("operating"):
        state = "not_operating" if suffix.endswith("nonoperating") else "operating"
        site["official_devices"]["entries"] = [{"official": True, "relevant": True,
            "source_ref": "synthetic device for software test",
            "state_by_frame": {str(i): state for i in range(9)}}]
    return site


def build():
    base = json.loads(BASE.read_text())
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        spec = json.loads(json.dumps(base))
        files = spec["files"]
        trace = [json.loads(line) for line in files["trace.jsonl"].splitlines()]
        mapping = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
        if len(trace) != len(mapping) or len(trace) != 9:
            raise ValueError("Diagnostic graph timebase differs")
        site = site_packet(case)
        point = ([0.5, 2] if suffix.startswith("destination_occupied") else
                 [3, 2] if suffix.startswith("opposite_") else
                 [0.5, 6] if suffix == "outside_crosswalk_absent" else [3, 6])
        ego, pedestrian, clocks, cameras = [], [], [], []
        for i, (body, frame) in enumerate(zip(trace, mapping)):
            common = {"frame": i, "elapsed_s": i / 20,
                      "native_frame": frame["carla_frame"],
                      "native_elapsed_s": frame["time_s"]}
            ego.append({**common, "actor_id": 101,
                        "classification": "motor_vehicle_driver",
                        "body_center_xy_m": [body["position"]["x"], body["position"]["y"]],
                        "heading_deg": body["heading_deg"],
                        "speed_mps": body["speed_mps"], "brake": True})
            pedestrian.append({**common, "actor_id": 202,
                               "classification": "pedestrian", "body_center_xy_m": point})
            clocks.append(common)
            cameras.append({**common, "views": {v["path"].removesuffix(".mkv"):
                            {"path": v["path"], "source": "generated_diagnostic_video"}
                            for v in spec["videos"]}})
        exception = {"case_id": case, "status": "none_identified",
                     "source_refs": ["synthetic exception review for software test"],
                     "diagnostic_fixture": True}
        contents = {"site": site, "ego": ego, "pedestrian": pedestrian,
                    "frame_map": clocks, "camera_manifest": cameras,
                    "exception_review": exception}
        source_index = {"format": "c111610-diagnostic-source-index-v1",
                        "case_id": case, "map_name": site["map_name"],
                        "diagnostic_fixture": True, "physical_acceptance_claimed": False,
                        "files": {}}
        for name, value in contents.items():
            data = text(value)
            files["capture/" + name + ".json"] = data
            source_index["files"][name] = {"path": name + ".json",
                                           "sha256": sha(data.encode()),
                                           "source": "diagnostic_synthetic"}
        files["capture/source-index.json"] = text(source_index)
        spec_path = ROOT / "diagnostics" / suffix / "specification.json"
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(json.dumps(spec, separators=(",", ":")) + "\n")
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-source.json",
                               "source": str(spec_path.relative_to(REPO)),
                               "sha256": sha(spec_path.read_bytes())}],
                  "generator": {"source": str(spec_path.relative_to(REPO)),
                                "sha256": sha(spec_path.read_bytes())}}
        recipe_path = spec_path.parent / "fixture-recipe.json"
        recipe_path.write_text(text(recipe))
        entry["fixture_recipe"] = str(recipe_path.relative_to(REPO))
    manifest_path.write_text(text(manifest))
    return manifest


if __name__ == "__main__":
    value = build()
    print(len(value["cases"]), "labelled synthetic exact-case compatibility recipes")
