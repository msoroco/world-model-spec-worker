"""Build nine-frame source-sealed software fixtures for exact parked cases."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from parked_activity import measure_original_activity

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def dump(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def build():
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if ".runtime-work" not in scratch.parts:
        raise ValueError("diagnostic scratch must be under .runtime-work")
    scratch.mkdir(parents=True, exist_ok=True)
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    base = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    base_mapping = [json.loads(line) for line in base["files"]["video_frames.jsonl"].splitlines() if line]
    if len(base_mapping) != 9:
        raise ValueError("pinned diagnostic fixture frame count changed")
    highway = [[-100, -10], [100, -10], [100, 10], [-100, 10]]
    bay = [[-15, -9], [5, -9], [5, -3], [-15, -3]]
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        variant = case_id.removeprefix(HERE.name + "__")
        spec = json.loads(json.dumps(base))
        files = spec["files"]
        frames = [{"frame": index, "time_s": index / 20,
                   "native_frame": row["carla_frame"], "native_time_s": row["time_s"]}
                  for index, row in enumerate(base_mapping)]
        approach = variant not in ("rear_clear",)
        wait = variant.endswith("wait")
        nonconflict = variant == "opposing_nonconflict"
        start_moving = 5 if wait else 2
        approach_end = 4 if wait else 7
        rows = []
        for index, frame in enumerate(frames):
            rows.append({
                "source_kind": "synthetic_fixture", "case_id": case_id,
                "frame": index, "time_s": index / 20,
                "native_frame": frame["native_frame"],
                "native_time_s": frame["native_time_s"],
                "ego_vehicle_id": "ego", "other_vehicle_id": "other",
                "driver_actor_id": "driver",
                "ego_center_xy_m": [-8 + max(index - start_moving, 0), -6],
                "other_center_xy_m": [-20 + 2 * index, -2],
                "ego_speed_mps": 0.0 if index < start_moving else 1.0,
                "other_speed_mps": 2.0 if approach else 0.0,
                "ego_in_reviewed_parking_bay": index < start_moving,
                "ego_on_public_highway": True,
                "parking_permitted_at_time": True,
                "driver_in_control": True,
                "other_approaching": approach and index < approach_end,
                "paths_overlap": (index in (3, 4) and not wait and approach and not nonconflict),
                "passenger_exchange": False, "goods_exchange": False,
            })
        activity = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
        seal = {"format": "diagnostic-parked-activity-seal", "case_id": case_id,
                "history_sha256": sha(activity), "frame_count": 9, "rate_hz": 20}
        temp_activity = scratch / (variant + "-diagnostic-activity.jsonl")
        temp_seal = scratch / (variant + "-diagnostic-activity-seal.json")
        temp_activity.write_text(activity)
        temp_seal.write_text(dump(seal))
        measured = measure_original_activity(temp_activity, temp_seal, case_id, diagnostic=True)
        sources = {key: {"path": key + ".txt", "sha256": sha(files["road.xodr"])} for key in
                   ("map", "highway_boundary", "dedication", "public_use",
                    "parking_permission", "vehicle_blueprint", "approach_route")}
        site = {"case_id": case_id, "source_kind": "synthetic_fixture",
                "public_highway_status": True, "public_dedication_reviewed": False,
                "public_vehicular_use_reviewed": False,
                "parking_permitted_at_capture_time": False,
                "reviewed_sources": sources,
                "highway_polygon_xy_m": highway, "parking_bay_polygon_xy_m": bay,
                "parked_vehicle_center_xy_m": [-8, -6],
                "ego_departure_entry_xy_m": [0, -2],
                "ego_departure_exit_xy_m": [30, -2]}
        plan = {"case_id": case_id, "variant": variant,
                "ego_initial_parked_center_xy_m": [-8, -6],
                "ego_departure_route_xy_m": [[-8, -6], [0, -2], [30, -2]],
                "other_approach_kind": "rear" if variant.startswith("rear") else "opposing",
                "controller_request": variant,
                "capture": {"rate_hz": 20, "frames": 900, "duration_s": 45,
                            "cameras": ["overview", "approach", "reference_corner", "driver_reference"]}}
        source_files = {
            "site.json": dump(site), "plan.json": dump(plan),
            "actors.json": dump({"ego_vehicle_id": "ego", "other_vehicle_id": "other",
                                  "driver_actor_id": "driver"}),
            "activity-seal.json": dump(seal),
            "frame-map.json": dump({"case_id": case_id, "frames": frames}),
            "activity-measurement.json": dump(measured),
        }
        inventory = {"case_id": case_id, "source_kind": "synthetic_fixture",
                     "frame_count": 9, "rate_hz": 20, "diagnostic_fixture": True,
                     "physical_completion": False, "media": {},
                     "map_sha256": sha(files["road.xodr"]),
                     "activity_sha256": sha(activity),
                     "source_sha256": {name: sha(content) for name, content in source_files.items()}}
        for name, content in source_files.items():
            files["original-attempt/" + name] = content
        files["original-attempt/activity.jsonl"] = activity
        files["original-attempt/road.xodr"] = files["road.xodr"]
        files["original-attempt/inventory.json"] = dump(inventory)
        files["fixture-provenance.json"] = dump({"diagnostic_fixture": True,
                                                  "physical_acceptance_claimed": False,
                                                  "scope": "nine-frame synthetic software protocol"})
        spec_path = HERE / ("diagnostic-" + variant + ".json")
        spec_path.write_text(json.dumps(spec, separators=(",", ":")) + "\n")
        reference = {"source": str(spec_path.relative_to(REPO)),
                     "sha256": sha(spec_path.read_bytes())}
        recipe_path = HERE / ("diagnostic-" + variant + "-recipe.json")
        recipe_path.write_text(dump({"format": "worker-fixture-recipe",
                                     "sources": [{"path": "diagnostic-input.json", **reference}],
                                     "generator": reference}))
        entry["fixture_recipe"] = str(recipe_path.relative_to(REPO))
    manifest_path.write_text(dump(manifest))
    return len(manifest["cases"])


if __name__ == "__main__":
    print(build())
