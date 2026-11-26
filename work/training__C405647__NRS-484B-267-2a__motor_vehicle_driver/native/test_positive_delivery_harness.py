"""Exercise the positive structural audit path with clearly synthetic inputs.

This harness cannot establish original Native provenance or physical acceptance.
It writes all temporary source material beneath .runtime-work.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
from delivery_audit import VIEWS, audit, audit_structure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(suffix="a"):
    if ".runtime-work" not in os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""):
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    source = REPO / ".runtime-work" / ("c405647-selected-" + suffix + "-compat-v3")
    root = REPO / ".runtime-work" / ("c405647-" + suffix + "-delivery-positive-harness")
    root.mkdir(parents=True, exist_ok=True)
    case = "training__C405647__NRS-484B-267-2a__motor_vehicle_driver__selected_d6045110__condition_" + suffix
    for name in ("video_frames.jsonl", "overview.mkv", "approach.mkv",
                 "reference_corner.mkv", "driver_reference.mkv"):
        shutil.copy2(source / name, root / name)
    shutil.copy2(source / "raw.mkv", root / "primary.mkv")
    shutil.copy2(source / "converted/trace.json", root / "trace.json")
    rows = [json.loads(line) for line in (source / "emergency_observations.jsonl").read_text().splitlines()]
    for row in rows:
        row["source_kind"] = "original_native_observation"
    (root / "emergency_observations.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    result = json.loads((source / "result.json").read_text())
    result["provenance_kind"] = "original_native"
    result["cpu_harness_only"] = True
    (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    (root / "capture-seal.json").write_text(json.dumps({"cpu_harness_only": True}) + "\n")
    (root / "pixel-review.json").write_text(json.dumps({
        "source_video_sha256": sha(root / "primary.mkv"),
        "camera_visibility_confirmed": True,
        "qualifying_flashing_pixels_confirmed": True,
        "moving_vehicle_pixels_confirmed": True,
        "reviewer": "synthetic_cpu_harness", "review_method": "mock positive branch only"
    }, indent=2) + "\n")
    inventory = {name: sha(root / name) for name in
                 ("result.json", "capture-seal.json", "video_frames.jsonl",
                  "emergency_observations.jsonl", "trace.json", "primary.mkv",
                  "pixel-review.json", *(view + ".mkv" for view in VIEWS))}
    sys.path.insert(0, str(REPO / "runtime"))
    from scenario_pipeline.worker_exchange.media import audit as decode
    receipt = root / "source-decode.json"
    if receipt.exists():
        receipt.unlink()
    decode(root / "primary.mkv", 600, mapping_sha256=inventory["video_frames.jsonl"],
           receipt=receipt)
    request = {
        "case_id": case, "source_kind": "original_native_observation",
        "source_sha256": inventory, "source_decode_receipt_path": str(receipt),
        "authorization_source_id": "synthetic-harness:authorization",
        "flashing_equipment_source_id": "synthetic-harness:equipment",
        "officer_direction_source_id": "synthetic-harness:officer",
        "road_context_source_id": "synthetic-harness:road",
        "weather_context_source_id": "synthetic-harness:weather",
        "officer_directed": False,
        "physical_review": {"source_result_sha256": inventory["result.json"],
                            "native_capture_seal_sha256": inventory["capture-seal.json"],
                            "setup_confirmed": True, "behavior_confirmed": True,
                            "maneuver_confirmed": True,
                            "reviewer": "synthetic_cpu_harness",
                            "review_method": "mock positive branch only"},
        "auditor_mode": "synthetic_cpu_harness",
    }
    checked = audit_structure(root, request)
    if checked["frames"] != 600 or not all(checked["checks"].values()):
        raise ValueError("Structural positive path incomplete")
    try:
        audit(root, request)
    except ValueError as exc:
        if "Native capture seal does not verify original acquisition" not in str(exc):
            raise
    else:
        raise ValueError("Production audit accepted synthetic harness")
    return {"format": "c405647-delivery-audit-cpu-harness-v1",
            "case_id": case, "structural_positive_passed": True,
            "production_acceptance_rejected": True,
            "synthetic_cpu_harness_only": True, "original_native_observed": False,
            "physical_acceptance_claimed": False, "legal_outcome_claimed": False}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
