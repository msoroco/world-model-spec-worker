"""Bind the exact reference primary source tree to a pinned offline manifest."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
assignment = root.parent.name
case = assignment + "__reference"
files = ["runner.py", "native_capture.py", "saved_source.py", "sight_speed_measure.py",
         "prove_sight_speed_measure.py", "prove_saved_source.py",
         "config.json", "tests/test_offline.py"]
construction = {
    "case_id": case, "cell_id": "C24758", "law_id": "LVMC-11-16-040",
    "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
    "status": "draft_saved_source_only_physical_unverified",
    "recording_description": {"duration_s": 30, "rate_hz": 20,
                              "camera_names": ["overview", "approach", "reference_corner", "driver_reference"],
                              "measurement": "last 100 ft sight and observed traversal speed"},
    "files": [{"path": f, "content": (root / f).read_text()} for f in files]
}
path = root / "primary-construction.json"
path.write_text(json.dumps(construction, indent=2) + "\n")
digest = hashlib.sha256(path.read_bytes()).hexdigest()
manifest = {"format": "worker-draft-offline-manifest-v1", "assignment_id": assignment,
            "cases": [{"case_id": case, "kind": "draft",
                       "construction": "primary-construction.json",
                       "construction_sha256": digest,
                       "candidate_risk": {"status": "physical",
                                          "reason": "Blind-corner occlusion and driver-view framing require original Native tuning"},
                       "candidates": []}]}
(root / "draft-primary-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(digest)
