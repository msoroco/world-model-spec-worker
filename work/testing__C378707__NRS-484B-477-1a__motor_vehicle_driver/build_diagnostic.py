"""Build source-sealed nine-frame software fixtures for exact alley cases."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from alley_activity import measure_original_activity

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def dump(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def sha(raw):
    if isinstance(raw, str):
        raw = raw.encode()
    return hashlib.sha256(raw).hexdigest()


def build():
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if ".runtime-work" not in scratch.parts:
        raise ValueError("diagnostic build scratch must be under .runtime-work")
    scratch.mkdir(parents=True, exist_ok=True)
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    base = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    base_mapping = [json.loads(line) for line in base["files"]["video_frames.jsonl"].splitlines() if line]
    if len(base_mapping) != 9:
        raise ValueError("pinned diagnostic smoke fixture frame count changed")
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        variant = case_id.removeprefix(HERE.name + "__")
        spec = json.loads(json.dumps(base))
        files = spec["files"]
        frames = [{"frame": index, "time_s": index / 20,
                   "native_frame": row["carla_frame"], "native_time_s": row["time_s"]}
                  for index, row in enumerate(base_mapping)]
        ordinance = variant == "ordinance_passenger_authorized"
        source_rows = []
        for index, frame in enumerate(frames):
            passenger = (index in (4, 5, 6) and variant in
                         ("passenger_active_stop", "ordinance_passenger_authorized")) or (
                         index in (6, 7) and variant in
                         ("passenger_wait_stand", "passenger_driver_exit_park"))
            goods = (index in (4, 5, 6) and variant == "goods_active_load") or (
                    index in (4, 6) and variant == "goods_wait_interrupted")
            source_rows.append({"source_kind": "synthetic_fixture", "case_id": case_id,
                                "frame": index, "time_s": index / 20,
                                "native_frame": frame["native_frame"],
                                "native_time_s": frame["native_time_s"],
                                "ego_vehicle_id": "ego", "passenger_actor_id": "passenger",
                                "goods_actor_id": "goods", "driver_actor_id": "driver",
                                "ego_speed_mps": 0.0 if index >= 3 else 1.0,
                                "ego_xy_m": [float(index), 0.0],
                                "in_business_alley": True,
                                "ordinance_reviewed_applicable": ordinance,
                                "passenger_contact": passenger, "goods_contact": goods,
                                "driver_in_vehicle": not (variant == "passenger_driver_exit_park" and index >= 5),
                                "door_open": passenger})
        activity = "".join(json.dumps(row, sort_keys=True) + "\n" for row in source_rows)
        seal = {"format": "diagnostic-alley-activity-seal", "case_id": case_id,
                "history_sha256": sha(activity), "frame_count": 9, "rate_hz": 20}
        (scratch / "diagnostic-activity.jsonl").write_text(activity)
        (scratch / "diagnostic-activity-seal.json").write_text(dump(seal))
        measured = measure_original_activity(scratch / "diagnostic-activity.jsonl",
                                             scratch / "diagnostic-activity-seal.json",
                                             case_id, diagnostic=True)
        site = {"case_id": case_id, "source_kind": "synthetic_fixture",
                "alley_kind": "business_district_alley", "business_district_reviewed": False,
                "reviewed_sources": {"map": {"path": "road.xodr",
                                              "sha256": sha(files["road.xodr"])}}}
        source_files = {"site.json": dump(site),
                        "plan.json": dump({"case_id": case_id, "diagnostic_fixture": True}),
                        "actors.json": dump({"ego_vehicle_id": "ego", "passenger_actor_id": "passenger",
                                             "goods_actor_id": "goods", "driver_actor_id": "driver"}),
                        "activity-seal.json": dump(seal),
                        "frame-map.json": dump({"case_id": case_id, "frames": frames}),
                        "activity-measurement.json": dump(measured)}
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
        reference = {"source": str(spec_path.relative_to(REPO)), "sha256": sha(spec_path.read_bytes())}
        recipe_path = HERE / ("diagnostic-" + variant + "-recipe.json")
        recipe_path.write_text(dump({"format": "worker-fixture-recipe",
                                     "sources": [{"path": "diagnostic-input.json", **reference}],
                                     "generator": reference}))
        entry["fixture_recipe"] = str(recipe_path.relative_to(REPO))
    manifest_path.write_text(dump(manifest))
    return len(manifest["cases"])


if __name__ == "__main__":
    print(build())
