"""Materialize five exact protected-lane delivery constructions."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
LAW = "NRS-486-341"
SOURCE_FILES = ("runner.py", "original_capture.py", "scene_review.py", "lane_use.py",
                "analysis.py", "case-plan.json", "tests/test_lane_use.py",
                "tests/test_scene_review.py")
CAMERAS = [{"name": name, "width": width, "height": height,
            "pose_strategy": strategy, "fov_deg": 90}
           for name, width, height, strategy in (
               ("overview", 1920, 1080, "fixed view of both one-way lanes and protected actor"),
               ("approach", 1280, 720, "ego approach and sourced lane boundary"),
               ("reference_corner", 1280, 720, "original body-box relation to protected lane"),
               ("driver_reference", 1280, 720, "ego-mounted forward participant view"))]
CHANNELS = ("occupied_lane", "body_intrusion", "protected_motion",
            "participant_class", "four_camera_visibility")
CONTEXT = ("jurisdiction", "site_source", "chapter_vehicle_classification_source")
RECORDING = {
    "channels": [{"name": name, "unit": "original-frame structured record", "sampling_rate_hz": 20,
                  "method": "source-bound original Native participant and map readback",
                  "time_window": "entire one-way 45s encounter",
                  "reference_frame": "original CARLA frame and elapsed time",
                  "uncertainty": "20 Hz sampling; legal full-use judgment and pixels need independent review"}
                 for name in CHANNELS],
    "context_inputs": [{"name": name, "unit": "source packet",
                        "method": "independently reviewed original source bytes"} for name in CONTEXT],
    "limitations": ["Body intrusion is physical context, not a legal deprivation cutoff.",
                    "Actual protected motion, pixels and source classifications require Native review."]}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def bundle(case, ids, start_shift):
    cid = case["case_id"]
    config = {"assignment_id": AID, "selected_case_id": cid, "supported_case_ids": ids,
              "law_id": LAW, "cell_id": "C147339", "actor": "motor_vehicle_driver",
              "rate_hz": 20, "duration_s": 45, "required_atoms": [], "source_packets": [],
              "cameras": CAMERAS, "engineering": {"ego_start_shift_m": start_shift},
              "physical_completion": {"criterion": "travel_progress", "motion_source": "trace.jsonl",
                                      "position_key": "position_m", "minimum_progress_m": 3,
                                      "minimum_samples": 2, "engineering_tolerances_not_legal": True},
              "case": {"case_id": cid, "protected_kind": case["protected_kind"],
                       "ego_path": case["ego_path"],
                       "protected_driven": case["protected_driven"],
                       "recording_description": RECORDING}}
    files = [{"path": name, "source": str((ROOT / name).relative_to(REPO)),
              "content": (ROOT / name).read_text(encoding="utf-8")}
             for name in SOURCE_FILES]
    files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
    construction = {"law_id": LAW, "cell_id": "C147339", "actor": "motor_vehicle_driver",
                    "case_id": cid, "entrypoint": "runner.py", "files": files,
                    "measurement_plan": [{"name": "protected_lane_use", "method": "analysis.analyze",
                                          "sources": ["protected-lane-history.jsonl",
                                                      "protected-lane-scene.json",
                                                      "trace.jsonl", "video_frames.jsonl"]}],
                    "recording_description": RECORDING,
                    "static_checks": ["reviewed original public highway and one-way multilane geometry",
                                      "distinct protected and ego Native actors and chapter classifications",
                                      "source-gated ordered adjacent/edge/deep ego body intrusion"],
                    "termination_rules": ["45 seconds of original 20 Hz protected-lane encounter"],
                    "mechanisms": ["source-gated reviewed original map, lane pair and routes",
                                   "two vehicle spawn and per-participant motion controller",
                                   "four synchronized original cameras and frame map",
                                   "saved-only source-bound finalizer"]}
    return config, construction


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
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
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "status": "source_gated_draft", "cases": []}
    for index, case in enumerate(plan["cases"]):
        suffix = case["case_id"].split("__")[-1]
        primary = ROOT if index == 0 else ROOT / "cases" / suffix
        fallback = ROOT / "cases" / suffix / "fallback1"
        def digest(path):
            return hashlib.sha256(path.read_bytes()).hexdigest()
        manifest["cases"].append({
            "case_id": case["case_id"], "kind": "delivery",
            "construction": str((primary / "construction.json").relative_to(ROOT)),
            "construction_sha256": digest(primary / "construction.json"),
            "fixture_recipe": "work/" + AID + "/diagnostic-" + suffix + "-recipe.json",
            "measurement_contract": "measurement-contract.json",
            "measurement_procedure": {"entrypoint": "analysis.py"},
            "source_gate": "original reviewed public highway, one-way lanes, routes, vehicle classes and source bytes required",
            "candidate_risk": {"status": "physical", "reason": case["physical_risk"]["reason"]},
            "candidates": [{"id": "fallback1",
                            "construction": str((fallback / "construction.json").relative_to(ROOT)),
                            "construction_sha256": digest(fallback / "construction.json"),
                            "trigger": {"source": "original Native trace and four cameras",
                                        "metric": "ego progress and protected-body visibility",
                                        "failure_condition": "original review finds ego spawn conflict or participant obscured"},
                            "changed_knobs": ["ego_start_shift_m"]}]})
    write(ROOT / "execution-manifest.json", manifest)


if __name__ == "__main__":
    main()
