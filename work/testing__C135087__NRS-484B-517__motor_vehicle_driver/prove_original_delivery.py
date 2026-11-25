"""CPU contract probe for the original delivery gate; never physical evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from audit_original_delivery import audit
from stand import SourceError


HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[1] / ".runtime-work"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(case_id, negative=False):
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entry = next((row for row in manifest["cases"] if row["case_id"] == case_id), None)
    if entry is None:
        raise ValueError("exact selected case required")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix="c135087-delivery-probe-") as directory:
        root = Path(directory)
        selection = {"format": "worker-candidate-selection", "candidate_id": "primary",
                     "case_id": case_id, "construction_sha256": entry["construction_sha256"],
                     "manifest_sha256": sha(manifest_path)}
        (root / "candidate-selection.json").write_text(json.dumps(selection) + "\n")
        for name in ("site-original.json", "vehicle-original.json",
                     *(camera + ".mkv" for camera in CAMERAS)):
            (root / name).write_text("MOCK ONLY " + name + "\n")
        review = {"source": "independent_original_site_vehicle_video_review",
                  "reviewer": "mock_probe_only", "case_id": case_id,
                  "reviewed_site_sha256": sha(root / "site-original.json"),
                  "reviewed_vehicle_sha256": sha(root / "vehicle-original.json"),
                  "official_stand_designation_source_reviewed": True,
                  "stand_sign_source_reviewed": True,
                  "subject_passenger_vehicle_source_reviewed": True,
                  "entrant_taxicab_source_reviewed": True,
                  "video_sha256": {camera: sha(root / (camera + ".mkv")) for camera in CAMERAS},
                  "reviewed_frame_ids": [0, 450, 899],
                  "subject_and_entrant_visible": True,
                  "passenger_loading_visible": True,
                  "stand_and_sign_visible": True,
                  "physical_motion_completed": True}
        if negative:
            review["stand_sign_source_reviewed"] = False
        packet = root / "review.json"
        packet.write_text(json.dumps(review) + "\n")
        ref = {"path": packet.name, "sha256": sha(packet)}
        source = {"case_id": case_id, "measurements": {"source_frame_count": 900},
                  "attempt_source_sha256": "a" * 64, "decoded_camera_frames": 3600}
        with patch("audit_original_delivery.extract", return_value=source) as original_audit:
            result = audit(case_id, root, ref)
            original_audit.assert_called_once()
            if result["case_id"] != case_id or result["legal_verdict_claimed"]:
                raise ValueError("mock delivery contract changed")
    return "mock-only original delivery gate wiring passed for " + case_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative-missing-review", action="store_true")
    args = parser.parse_args()
    try:
        print(probe(args.case, args.negative_missing_review))
    except SourceError as error:
        print(str(error))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
