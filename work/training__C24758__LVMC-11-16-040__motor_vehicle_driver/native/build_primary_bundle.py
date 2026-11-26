"""Bind the exact reference primary source tree to a pinned offline manifest."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
assignment = root.parent.name
files = ["runner.py", "native_capture.py", "ray_inventory.py", "context_review.py", "finalize.py", "saved_source.py", "sight_speed_measure.py",
         "prove_sight_speed_measure.py", "prove_saved_source.py",
         "config.json", "tests/test_offline.py"]
for suffix, target_speed in (("reference", 6.2), ("at_15", 6.7056), ("contrast", 7.2)):
    case = assignment + "__" + suffix
    config = json.loads((root / "config.json").read_text())
    config["case_id"] = case
    config["selected_case_id"] = case
    config["supported_case_ids"] = [assignment + "__" + name for name in ("reference", "at_15", "contrast")]
    config["case"] = {"case_id": case}
    config["target_speed_mps"] = target_speed
    config["requested_speed_mps"] = target_speed
    config["case"]["recording_description"] = json.loads((root / "recording-description.json").read_text())
    construction = {
        "case_id": case, "cell_id": "C24758", "law_id": "LVMC-11-16-040",
        "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
        "status": "draft_saved_source_only_physical_unverified",
        "recording_description": json.loads((root / "recording-description.json").read_text()),
        "files": [{"path": f, "content": json.dumps(config, indent=2) + "\n"
                   if f == "config.json" else (root / f).read_text()} for f in files]
    }
    path = root / ("primary-construction.json" if suffix == "reference" else suffix + "-construction.json")
    path.write_text(json.dumps(construction, indent=2) + "\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    fallback = json.loads(json.dumps(construction))
    fallback_config = dict(config, throttle_gain=0.16, brake_gain=0.22)
    for item in fallback["files"]:
        if item["path"] == "config.json":
            item["content"] = json.dumps(fallback_config, indent=2) + "\n"
    fallback_path = root / (suffix + "-fallback1-construction.json")
    fallback_path.write_text(json.dumps(fallback, indent=2) + "\n")
    fallback_digest = hashlib.sha256(fallback_path.read_bytes()).hexdigest()
    manifest = {"format": "worker-draft-offline-manifest-v1", "assignment_id": assignment,
                "cases": [{"case_id": case, "kind": "draft",
                           "construction": path.name,
                           "construction_sha256": digest,
                           "candidate_risk": {"status": "physical",
                                              "reason": "Blind-corner occlusion and driver-view framing require original Native tuning"},
                           "candidates": [{"id": "fallback1",
                                           "construction": fallback_path.name,
                                           "construction_sha256": fallback_digest,
                                           "trigger": {"source": "original Native ego velocity and controller readback",
                                                       "metric": "observed speed tracking after first 100 frames",
                                                       "failure_condition": "fewer than 400 of the next 500 frames within 1 mph of the unchanged requested speed, after source integrity review"},
                                           "changed_knobs": ["throttle proportional gain 0.12 to 0.16",
                                                             "brake proportional gain 0.18 to 0.22"]}]}]}
    manifest_path = root / ("draft-primary-manifest.json" if suffix == "reference" else "draft-" + suffix + "-manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(suffix, digest, "fallback1", fallback_digest)
