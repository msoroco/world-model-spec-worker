"""Join an external original-pixel review to a sealed elevator attempt.

This checks evidence custody and observation completeness. It does not decide
whether the statute applies or infer observations from a diagnostic fixture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from independent_delivery_audit import CAMERAS, audit
from parking import CASES, measure_original_history
from reviewed_site import verify


OBSERVATIONS = (
    "sidewalk_elevator_identity", "elevator_front_and_side_edges",
    "ego_vehicle_body", "one_way_approach", "curb_relation",
    "stop_stand_park_activity", "traffic_conflict", "police_direction",
    "traffic_device_direction", "camera_visibility",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review(attempt: Path, site_packet: Path, source_root: Path,
           reviewer_packet: Path, reviewer_sha256: str) -> dict:
    attempt = Path(attempt).resolve()
    reviewer_packet = Path(reviewer_packet).resolve()
    if reviewer_packet.is_relative_to(attempt) or attempt.is_relative_to(reviewer_packet):
        raise ValueError("reviewer packet must be external to original attempt")
    if _sha(reviewer_packet) != reviewer_sha256:
        raise ValueError("external reviewer packet hash differs")
    source_packet = verify(site_packet, source_root)
    delivery = audit(attempt, site_packet, source_root)
    claim = json.loads(reviewer_packet.read_text())
    if claim.get("format") != "sidewalk-elevator-original-pixel-review" or not claim.get("reviewer") or not claim.get("citation"):
        raise ValueError("independent original pixel review identity missing")
    if (claim.get("case_id") != delivery["case_id"] or
            claim.get("site_packet_sha256") != delivery["site_packet_sha256"] or
            claim.get("source_hashes") != delivery["source_hashes"]):
        raise ValueError("pixel review original source binding differs")
    observations = claim.get("observations", {})
    if set(observations) != set(OBSERVATIONS):
        raise ValueError("pixel review observations incomplete")
    for name, item in observations.items():
        if not isinstance(item, dict) or item.get("observed") not in (True, False):
            raise ValueError("pixel review observation missing: " + name)
        camera = item.get("camera")
        frame = item.get("original_frame")
        if camera not in CAMERAS or type(frame) is not int or not 0 <= frame < 900:
            raise ValueError("pixel review frame or camera invalid: " + name)
        if item.get("camera_sha256") != delivery["source_hashes"][camera + ".mkv"]:
            raise ValueError("pixel review camera source changed: " + name)
        if not item.get("note") or not item.get("reviewer"):
            raise ValueError("pixel review explanation missing: " + name)
    case_name = delivery["case_id"].removeprefix(source_packet["assignment_id"] + "__")
    case = next(item for item in CASES if item.id == case_name)
    required = {"sidewalk_elevator_identity", "elevator_front_and_side_edges",
                "ego_vehicle_body", "one_way_approach", "curb_relation",
                "stop_stand_park_activity", "camera_visibility"}
    exception_name = {
        "lawful_traffic_conflict": "traffic_conflict",
        "police_direction": "police_direction",
        "traffic_device_direction": "traffic_device_direction",
    }.get(case.exception)
    if exception_name:
        required.add(exception_name)
    if any(observations[name]["observed"] is not True for name in required):
        raise ValueError("required original physical observation absent")
    rows = [json.loads(line) for line in (attempt / "history.jsonl").read_text().splitlines()]
    measured = measure_original_history(rows, source_packet["site"], case)
    if measured["frame_count"] != 900:
        raise ValueError("original physical history duration differs")
    if case.region == "front" and measured["front_overlap_frames"] == 0:
        raise ValueError("original vehicle did not occupy elevator frontage")
    if case.region != "front" and case.region not in measured["observed_regions"]:
        raise ValueError("original vehicle did not occupy requested elevator side")
    activity = {"stop": "stopped", "stand": "standing", "park": "parked"}[case.activity]
    if activity not in measured["observed_activities"]:
        raise ValueError("original requested activity absent")
    return {"format": "sidewalk-elevator-physical-review-prepared",
            "case_id": delivery["case_id"],
            "reviewer_packet_sha256": reviewer_sha256,
            "site_packet_sha256": delivery["site_packet_sha256"],
            "source_hashes": delivery["source_hashes"],
            "frame_count": 900, "all_required_observations": True,
            "measured_min_side_gap_m": measured["min_side_gap_m"],
            "five_feet_m_reference": measured["five_feet_m_reference"],
            "legal_judgment": None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--site-packet", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--reviewer-packet", type=Path, required=True)
    parser.add_argument("--reviewer-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("physical review output already exists")
    result = review(args.attempt, args.site_packet, args.source_root,
                    args.reviewer_packet, args.reviewer_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
