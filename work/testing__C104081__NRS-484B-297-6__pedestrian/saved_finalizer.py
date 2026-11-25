"""Finalize one exact pedestrian bypass from sealed saved acquisition.

The result records measured histories and source hashes. It does not turn a
diagnostic fixture or an unreviewed Native capture into physical acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import ASSIGNMENT, CASE_EXPECTATIONS, CAMERAS, audit_saved
from saved_measurement import measure_saved


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_result(attempt: Path, case_id: str, *, diagnostic: bool = False,
                 decode_media: bool = True) -> dict:
    """Recompute measurements from the same files independently audited above."""
    attempt = Path(attempt)
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("unknown exact pedestrian case")
    suffix = case_id[len(ASSIGNMENT) + 2:]
    if suffix not in CASE_EXPECTATIONS:
        raise ValueError("unknown exact pedestrian case")
    audit = audit_saved(attempt, case_id, diagnostic=diagnostic,
                        decode_media=decode_media)
    measured = measure_saved(attempt, case_id)
    if audit["source_packet_sha256"] != measured["source_packet_sha256"]:
        raise ValueError("audit and measurement source packet differ")
    if audit["measured_observables"] != measured["observables"]:
        raise ValueError("audit and measurement observables differ")
    if audit["original_frame_count"] != measured["sample_count"]:
        raise ValueError("audit and measurement frame counts differ")
    observed = measured["observables"]
    expected = CASE_EXPECTATIONS[suffix]
    targets = (
        ("pedestrian_direction", expected[0], observed["pedestrian_direction"]),
        ("intervening_barrier_present", expected[1], observed["intervening_barrier_present"]),
        ("designated_lane_used", expected[2], observed["designated_lane_used"]),
        ("sidewalk_obstruction_end_m", expected[3], observed["sidewalk_obstruction_end_m"]),
        ("sidewalk_obstruction_kind", expected[4], observed["sidewalk_obstruction_kind"]),
    )
    source_hashes = dict(measured["source_sha256"])
    source_hashes["source-packet.json"] = measured["source_packet_sha256"]
    video = [audit["sealed_camera_media"][name]["path"] for name in CAMERAS]
    config_path = attempt / "config.json"
    if config_path.is_file():
        recording_description = json.loads(config_path.read_text()).get("recording_description")
    else:
        recording_description = None
    if recording_description is None and (attempt / "construction.json").is_file():
        recording_description = json.loads((attempt / "construction.json").read_text()).get("recording_description")
    if recording_description is None:
        recording_description = "Pedestrian sidewalk obstruction bypass at C104081"
    return {
        "case_id": case_id,
        "source_kind": measured["provenance_kind"],
        "diagnostic_fixture": measured["diagnostic_fixture"],
        "source_sha256": source_hashes,
        "measured_values": observed,
        "target_checks": [{
            "target": name, "requested": requested, "measured": value,
            "method": "sealed original frame, body, obstruction and traffic join",
            "tolerance": 0, "matched": value == requested,
            "physical_cause_confirmed": False,
            "cause_evidence": {"source_packet_sha256": measured["source_packet_sha256"],
                               "physical_review": "pending"},
        } for name, requested, value in targets],
        "setup_confirmed": False,
        "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved source measurement complete; physical review pending",
        "physical_failure_flags": {"physical_review_pending": True},
        "trace_reference": "pedestrian_history.jsonl",
        "video_references": video,
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": recording_description,
        "recording_evidence": [
            {"name": "saved_source_packet", "unit": "metadata", "reference": "source-packet.json"},
            {"name": "observed_obstruction", "unit": "structured", "reference": "obstruction_history.jsonl"},
            {"name": "observed_traffic", "unit": "structured", "reference": "traffic_history.jsonl"},
        ],
        "realized_observables": observed,
        "legal_judgment": "unresolved",
        "physical_acceptance": "not_assessed",
    }


def finalize(attempt: Path, case_id: str, *, diagnostic: bool = False,
             decode_media: bool = True) -> Path:
    from worker_exchange.native_output import write_result
    result = build_result(attempt, case_id, diagnostic=diagnostic,
                          decode_media=decode_media)
    return write_result(attempt, result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    path = finalize(args.attempt, args.case, diagnostic=args.diagnostic)
    print(json.dumps({"result": str(path), "sha256": _sha(path)}))


if __name__ == "__main__":
    main()
