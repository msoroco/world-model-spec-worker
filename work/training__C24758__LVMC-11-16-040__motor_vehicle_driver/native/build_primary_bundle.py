"""Bind the exact reference primary source tree to a pinned offline manifest."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
assignment = root.parent.name
files = ["runner.py", "native_capture.py", "ray_inventory.py", "context_review.py", "saved_source.py", "sight_speed_measure.py",
         "prove_sight_speed_measure.py", "prove_saved_source.py",
         "config.json", "tests/test_offline.py"]
for suffix, target_speed in (("reference", 6.2), ("contrast", 7.2)):
    case = assignment + "__" + suffix
    config = json.loads((root / "config.json").read_text())
    config["case_id"] = case
    config["selected_case_id"] = case
    config["supported_case_ids"] = [case]
    config["case"] = {"case_id": case}
    config["target_speed_mps"] = target_speed
    construction = {
        "case_id": case, "cell_id": "C24758", "law_id": "LVMC-11-16-040",
        "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
        "status": "draft_saved_source_only_physical_unverified",
        "recording_description": {"duration_s": 30, "rate_hz": 20,
                                  "camera_names": ["overview", "approach", "reference_corner", "driver_reference"],
                                  "measurement": "last 100 ft sight and observed traversal speed"},
        "files": [{"path": f, "content": json.dumps(config, indent=2) + "\n"
                   if f == "config.json" else (root / f).read_text()} for f in files]
    }
    path = root / ("primary-construction.json" if suffix == "reference" else "contrast-construction.json")
    path.write_text(json.dumps(construction, indent=2) + "\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {"format": "worker-draft-offline-manifest-v1", "assignment_id": assignment,
                "cases": [{"case_id": case, "kind": "draft",
                           "construction": path.name,
                           "construction_sha256": digest,
                           "candidate_risk": {"status": "physical",
                                              "reason": "Blind-corner occlusion and driver-view framing require original Native tuning"},
                           "candidates": []}]}
    manifest_path = root / ("draft-primary-manifest.json" if suffix == "reference" else "draft-contrast-manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(suffix, digest)
