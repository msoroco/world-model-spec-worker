"""Exercise both preparing audit paths with labelled synthetic source shapes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

from preparing_source_audit import VIEWS, audit, audit_structure

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE = HERE.parent.name + "__preparing_to_move__"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(branch):
    if ".runtime-work" not in os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""):
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    name = "movement" if branch == "visible_vehicle_movement" else "hand"
    source = REPO / ".runtime-work" / ("c405647-" + branch + "-primary-public-v8")
    root = REPO / ".runtime-work" / ("c405647-preparing-" + name + "-delivery-harness-v8")
    root.mkdir(parents=True, exist_ok=True)
    for name in ("video_frames.jsonl", *(view + ".mkv" for view in VIEWS)):
        shutil.copy2(source / name, root / name)
    shutil.copy2(source / "raw.mkv", root / "primary.mkv")
    rows = [json.loads(line) for line in (source / "preparing_observations.jsonl").read_text().splitlines()]
    for row in rows:
        row["source_kind"] = "original_native_observation"
    (root / "preparing_observations.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows))
    (root / "capture-seal.json").write_text(json.dumps({"cpu_harness_only": True}) + "\n")
    result = json.loads((source / "result.json").read_text())
    result["provenance_kind"] = "original_native"
    result["cpu_harness_only"] = True
    (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    hashes = {name: sha(root / name) for name in
              ("video_frames.jsonl", "preparing_observations.jsonl", "primary.mkv",
               *(view + ".mkv" for view in VIEWS))}
    review = {"case_id": BASE + branch, "activation_branch": branch,
              "source_kind": "original_native_observation", "source_sha256": hashes,
              "auditor_mode": "synthetic_cpu_harness",
              "pixel_review": {"source_video_sha256": hashes["primary.mkv"],
                               "reviewer": "synthetic_cpu_harness", "review_method": "mock structural branch only",
                               "branch": branch, "visible": True,
                               "vehicle_actor_id": 108, "first_visible_frame": 120,
                               "driver_actor_id": 109, "hand_signal_type": "left",
                               "hand_signal_actor_source_id": "synthetic-driver"},
              "source_witness": {"subject_approach_source_id": "synthetic-approach",
                                 "authorized_vehicle_source_id": "synthetic-vehicle",
                                 "vehicle_kind": "authorized_emergency_vehicle",
                                 "flashing_equipment_source_id": "synthetic-equipment",
                                 "flashing_pixel_source_id": "synthetic-lamp-pixels",
                                 "flashing_qualification_source_id": "synthetic-lamp-review",
                                 "officer_direction_source_id": "synthetic-officer",
                                 "road_context_source_id": "synthetic-road",
                                 "weather_context_source_id": "synthetic-weather",
                                 "officer_directed": False}}
    (root / "review.json").write_text(json.dumps(review, indent=2) + "\n")
    checked = audit_structure(root, review)
    if checked["frames"] != 600 or checked["first_visible_frame"] != 120:
        raise ValueError("Preparing structural positive path incomplete")
    try:
        audit(root, review)
    except ValueError as error:
        if "Native capture seal does not verify original acquisition" not in str(error):
            raise
    else:
        raise ValueError("Production audit accepted synthetic harness")
    return {"format": "c405647-preparing-delivery-cpu-harness-v1",
            "case_id": BASE + branch, "structural_positive_passed": True,
            "production_acceptance_rejected": True, "synthetic_cpu_harness_only": True,
            "original_native_observed": False, "physical_acceptance_claimed": False,
            "legal_outcome_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=(BASE + "visible_vehicle_movement",
                                          BASE + "visible_driver_hand_signal"))
    args = parser.parse_args()
    branches = [args.case[len(BASE):]] if args.case else [
        "visible_vehicle_movement", "visible_driver_hand_signal"]
    print(json.dumps([run(branch) for branch in branches], indent=2, sort_keys=True))
