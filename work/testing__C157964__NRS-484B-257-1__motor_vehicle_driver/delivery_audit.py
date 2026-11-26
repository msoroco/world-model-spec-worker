"""Independent, source-bound review of a selected original C157964 attempt.

The review packet is supplied outside the attempt and its expected SHA-256 comes
from the local reviewer. A diagnostic packet cannot be used as physical proof.
"""

import argparse
import hashlib
import json
from pathlib import Path

from saved_audit import audit_saved
from yield_view import CASES, require


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
OBSERVATIONS = ("yield_sign", "stop_line_absence", "crosswalk_absence",
                "nearest_view_sight", "ego_motion", "through_motion",
                "officer_control", "traffic_signal_control", "camera_visibility")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _inside(root, relative):
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute(),
            "review evidence path missing or absolute")
    path = (root / relative).resolve()
    require(path.is_relative_to(root) and path.is_file(),
            "review evidence path escapes or is missing")
    return path


def audit_original(attempt, review_packet, case, *, expected_site_packet_sha256,
                   expected_review_packet_sha256):
    """Require an independently pinned review of original frames and sources."""
    root = Path(attempt).resolve()
    source = audit_saved(root, case,
                         expected_site_packet_sha256=expected_site_packet_sha256)
    require(source["diagnostic_fixture"] is False,
            "diagnostic source cannot establish physical completion")
    review_path = Path(review_packet).resolve()
    require(review_path.is_file() and review_path != root / "review-packet.json" and
            not review_path.is_relative_to(root),
            "independent review packet must be outside attempt")
    review_bytes = review_path.read_bytes()
    require(expected_review_packet_sha256 and
            _sha(review_bytes) == expected_review_packet_sha256,
            "independent review packet hash differs")
    review = json.loads(review_bytes)
    require(review.get("format") == "c157964-original-physical-review-v1" and
            review.get("case_id") == case.case_id and
            review.get("native_seal_sha256") == source["native_seal_sha256"] and
            review.get("site_packet_sha256") == expected_site_packet_sha256 and
            review.get("diagnostic_fixture") is False,
            "review packet does not bind original exact attempt")
    require(review.get("reviewer") and review.get("reviewed_at") and
            review.get("source_kind") == "original_native_capture",
            "independent original reviewer identity missing")
    observations = review.get("observations")
    require(isinstance(observations, dict) and set(observations) == set(OBSERVATIONS),
            "physical review observations incomplete")
    camera_index = json.loads((root / "camera-index.json").read_text())
    rows = json.loads((root / "rows.json").read_text())
    frames = {row["original_frame"] for row in rows}
    evidence_root = review_path.parent.resolve()
    for name in OBSERVATIONS:
        item = observations[name]
        require(isinstance(item, dict) and item.get("observed") is True and
                item.get("reviewer_note") and item.get("source_sha256") and
                type(item.get("frame")) is int and item["frame"] in frames and
                item.get("camera") in VIEWS,
                "original physical observation missing: " + name)
        frame = item["frame"]
        require(any(entry["frame"] == frame for entry in camera_index[item["camera"]]),
                "review camera/frame join missing: " + name)
        evidence = _inside(evidence_root, item.get("evidence_path"))
        require(_sha(evidence.read_bytes()) == item["source_sha256"],
                "review evidence bytes changed: " + name)
    require(review.get("physical_completion") is True and
            review.get("legal_judgment") is None,
            "physical completion or unresolved legal judgment differs")
    return {"format": "c157964-independent-delivery-audit-v1",
            "case_id": case.case_id,
            "native_seal_sha256": source["native_seal_sha256"],
            "review_packet_sha256": _sha(review_bytes),
            "site_packet_sha256": expected_site_packet_sha256,
            "decoded_camera_frames": source["decoded_camera_frames"],
            "physical_completion": True, "legal_judgment": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--review-packet", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--expected-site-packet-sha256", required=True)
    parser.add_argument("--expected-review-packet-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    case = next((item for item in CASES if item.case_id == args.case), None)
    require(case is not None, "unknown exact yield case")
    require(not args.output.exists(), "retain prior independent delivery audit")
    result = audit_original(args.attempt, args.review_packet, case,
                            expected_site_packet_sha256=args.expected_site_packet_sha256,
                            expected_review_packet_sha256=args.expected_review_packet_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
