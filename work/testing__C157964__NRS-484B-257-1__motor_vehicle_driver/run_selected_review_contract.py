"""Exercise four original-review packet contracts with mocked source custody.

The original source audit is deliberately mocked: this is a structural CPU test,
not a claim that the synthetic captures contain physical roadway evidence.
"""

import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from delivery_audit import OBSERVATIONS, audit_original
from yield_view import CASES, require


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-root", required=True, type=Path)
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "review-contract receipt already exists")
    scratch = args.scratch.resolve()
    require(".runtime-work" in scratch.parts, "scratch must remain under .runtime-work")
    scratch.mkdir(parents=True, exist_ok=True)
    receipts = []
    for case in CASES:
        attempt = args.fixture_root / case.case_id / "original-attempt"
        site_hash = digest(attempt / "reviewed-site-packet.json")
        seal_hash = digest(attempt / "seal.json")
        first = json.loads((attempt / "camera-index.json").read_text())["overview"][0]
        evidence_dir = scratch / case.case_id
        evidence_dir.mkdir(exist_ok=True)
        evidence = evidence_dir / "observation.txt"
        evidence.write_text("Synthetic review contract fixture for " + case.case_id + "\n")
        observations = {
            name: {"observed": True, "reviewer_note": "Synthetic structural fixture",
                   "source_sha256": digest(evidence), "evidence_path": "observation.txt",
                   "frame": first["frame"], "camera": "overview",
                   "pixel_sha256": first["sha256"]}
            for name in OBSERVATIONS
        }
        packet = {"format": "c157964-original-physical-review-v1",
                  "case_id": case.case_id, "native_seal_sha256": seal_hash,
                  "site_packet_sha256": site_hash, "diagnostic_fixture": False,
                  "reviewer": "synthetic-cpu-contract", "reviewed_at": "2026-11-25T00:00:00Z",
                  "source_kind": "original_native_capture", "observations": observations,
                  "physical_completion": True, "legal_judgment": None}
        review_path = evidence_dir / "review.json"
        review_path.write_text(json.dumps(packet, sort_keys=True) + "\n")
        mocked = {"diagnostic_fixture": False, "native_seal_sha256": seal_hash,
                  "decoded_camera_frames": 3600}
        with patch("delivery_audit.audit_saved", return_value=mocked):
            positive = audit_original(attempt, review_path, case,
                                      expected_site_packet_sha256=site_hash,
                                      expected_review_packet_sha256=digest(review_path))
            require(positive["physical_completion"] is True,
                    "structural positive review rejected")
            packet["observations"].pop("camera_visibility")
            review_path.write_text(json.dumps(packet, sort_keys=True) + "\n")
            try:
                audit_original(attempt, review_path, case,
                               expected_site_packet_sha256=site_hash,
                               expected_review_packet_sha256=digest(review_path))
            except ValueError as exc:
                require("observations incomplete" in str(exc),
                        "unexpected missing-observation result")
                negative = str(exc)
            else:
                raise ValueError("missing review observation was accepted")
        receipts.append({"case_id": case.case_id,
                         "mocked_original_source_audit": True,
                         "positive_review_contract": True,
                         "missing_observation_rejection": negative})
    result = {"format": "c157964-selected-review-contract-cpu-v1",
              "source_kind": "synthetic_mocked_cpu_fixture",
              "original_physical_review": "unverified", "receipts": receipts}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"positive_contracts": len(receipts),
                      "missing_observation_negatives": len(receipts),
                      "original_physical_review": "unverified"}, sort_keys=True))


if __name__ == "__main__":
    main()
