"""Materialize eight exact adjacent-lane source-gated Native bundles."""
from __future__ import annotations

import json
from pathlib import Path

from author_semantics import RECORDING

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
LAW = "NRS-486-351-1"
SOURCE_FILES = ("runner.py", "original_capture.py", "scene_review.py", "lane_split.py", "analysis.py")
CAMERAS = [{"name": name, "width": width, "height": height,
            "pose_strategy": strategy, "fov_deg": 90}
           for name, width, height, strategy in (
               ("overview", 1920, 1080, "fixed view of both adjacent lanes and passage"),
               ("approach", 1280, 720, "ego entry and surveyed drivable split route"),
               ("reference_corner", 1280, 720, "body-box relation across lane boundary"),
               ("driver_reference", 1280, 720, "ego-mounted forward participant view"))]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def bundle(case, ids, shift_m):
    cid = case["case_id"]
    config = {"assignment_id": AID, "selected_case_id": cid,
              "supported_case_ids": ids, "law_id": LAW, "cell_id": "C145696",
              "actor": "motorcycle_or_moped_operator", "rate_hz": 20,
              "duration_s": 45, "required_atoms": [], "source_packets": [],
              "cameras": CAMERAS, "engineering": {"ego_start_shift_m": shift_m},
              "physical_completion": {"criterion": "travel_progress", "motion_source": "trace.jsonl",
                                      "position_key": "position_m", "minimum_progress_m": 3,
                                      "minimum_samples": 2, "engineering_tolerances_not_legal": True},
              "case": {**case["scenario_parameters"], "case_id": cid,
                       "recording_description": RECORDING}}
    files = [{"path": name, "source": str((ROOT / name).relative_to(REPO)),
              "content": (ROOT / name).read_text(encoding="utf-8")}
             for name in SOURCE_FILES]
    files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
    construction = {"law_id": LAW, "cell_id": "C145696",
                    "actor": "motorcycle_or_moped_operator", "case_id": cid,
                    "entrypoint": "runner.py", "files": files,
                    "measurement_plan": [{"name": "adjacent_lane_passage", "method": "analysis.analyze",
                                          "sources": ["lane-split-history.jsonl", "lane-split-scene.json",
                                                      "trace.jsonl", "video_frames.jsonl"]}],
                    "recording_description": RECORDING,
                    "static_checks": ["exact one-way adjacent lane and route geometry from reviewed map",
                                      "three actor IDs and source-backed motorcycle/moped classification",
                                      "independent police identity and performance-of-duty source hashes"],
                    "termination_rules": ["45 seconds of original 20 Hz movement and passage"],
                    "mechanisms": ["source-gated reviewed original map and lane pair",
                                   "separate ego and two adjacent-lane occupant Native actors",
                                   "per-participant motion controller and source readback",
                                   "four synchronized original cameras and original frame map",
                                   "saved-only source-bound finalizer"]}
    return config, construction


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    ids = [item["case_id"] for item in plan["cases"]]
    for index, case in enumerate(plan["cases"]):
        suffix = case["case_id"].split("__")[-1]
        primary = ROOT if index == 0 else ROOT / "cases" / suffix
        config, construction = bundle(case, ids, 0)
        write(primary / "config.json", config)
        write(primary / "construction.json", construction)
        fallback = ROOT / "cases" / suffix / "fallback1"
        config, construction = bundle(case, ids, -3)
        write(fallback / "config.json", config)
        write(fallback / "construction.json", construction)


if __name__ == "__main__":
    main()
