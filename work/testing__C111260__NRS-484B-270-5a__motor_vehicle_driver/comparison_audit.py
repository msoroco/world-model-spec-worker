"""Independent pair audit for bicycle encounter response comparisons."""

import argparse
import hashlib
import json
from pathlib import Path


def audit_pair(brake, maintain, minimum_frames=60):
    required = ("case_id", "map_sha256", "rider_kind", "rider_blueprint_id",
                "ego_route_sha256", "rider_route_sha256", "camera_plan_sha256",
                "duration_frames", "hz", "initial_ego_speed_mps", "initial_rider_speed_mps",
                "response", "observed_brake_peak", "original_history_sha256")
    for item in (brake, maintain):
        if any(key not in item or item[key] is None for key in required):
            raise ValueError("missing source-bound comparison evidence")
        if item["hz"] != 20 or item["duration_frames"] < minimum_frames:
            raise ValueError("comparison duration or sample rate unproved")
        if not item["original_history_sha256"] or len(item["original_history_sha256"]) != 64:
            raise ValueError("original history digest absent")
    for key in ("map_sha256", "rider_kind", "rider_blueprint_id", "ego_route_sha256",
                "rider_route_sha256", "camera_plan_sha256", "duration_frames", "hz"):
        if brake[key] != maintain[key]:
            raise ValueError("fixed comparison condition changed: " + key)
    for key in ("initial_ego_speed_mps", "initial_rider_speed_mps"):
        if abs(float(brake[key]) - float(maintain[key])) > 0.25:
            raise ValueError("initial speed condition changed: " + key)
    if brake["response"] != "brake" or maintain["response"] != "maintain":
        raise ValueError("response labels mismatched")
    if float(brake["observed_brake_peak"]) < 0.5 or float(maintain["observed_brake_peak"]) > 0.1:
        raise ValueError("declared response not observed")
    if brake["case_id"] == maintain["case_id"] or brake["original_history_sha256"] == maintain["original_history_sha256"]:
        raise ValueError("distinct source histories required")
    return {"comparison_complete": True, "rider_kind": brake["rider_kind"],
            "legal_judgment": "undetermined"}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def source_summary(attempt, *, diagnostic=False):
    root = Path(attempt)
    packet = json.loads((root / "encounter-packet.json").read_text())
    if packet.get("diagnostic_fixture") is not diagnostic:
        raise ValueError("comparison source provenance differs")
    for key in ("site", "history", "camera_frames"):
        ref = packet[key]
        if _sha(root / ref["path"]) != ref["sha256"]:
            raise ValueError("comparison original source changed: " + key)
    site = json.loads((root / "site.json").read_text())
    history = json.loads((root / "history.json").read_text())
    config = json.loads((root / "config.json").read_text())
    if not history or any(row.get("case_id") != packet["case_id"] for row in history):
        raise ValueError("comparison case history differs")
    return {"case_id": packet["case_id"], "map_sha256": site["map_sha256"],
            "rider_kind": site["rider"]["kind"],
            "rider_blueprint_id": site["rider"]["blueprint_id"],
            "ego_route_sha256": _canonical_sha(site["ego_route"]),
            "rider_route_sha256": _canonical_sha(site["rider_route"]),
            "camera_plan_sha256": _canonical_sha(config["cameras"]),
            "duration_frames": len(history), "hz": packet["hz"],
            "initial_ego_speed_mps": history[0]["ego_speed_mps"],
            "initial_rider_speed_mps": history[0]["rider_speed_mps"],
            "response": config["case"]["motorist_response"],
            "observed_brake_peak": max(row["ego_brake_observed"] for row in history
                                       if row.get("conflict_window_observed")),
            "original_history_sha256": _sha(root / "history.json")}


def audit_saved_pair(brake_attempt, maintain_attempt, *, diagnostic=False):
    brake = source_summary(brake_attempt, diagnostic=diagnostic)
    maintain = source_summary(maintain_attempt, diagnostic=diagnostic)
    result = audit_pair(brake, maintain, minimum_frames=9 if diagnostic else 900)
    result.update(diagnostic_fixture=diagnostic, brake_case_id=brake["case_id"],
                  maintain_case_id=maintain["case_id"],
                  source_histories=[brake["original_history_sha256"],
                                    maintain["original_history_sha256"]])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brake", required=True)
    parser.add_argument("--maintain", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit_saved_pair(args.brake, args.maintain,
                                      diagnostic=args.diagnostic), indent=2))


if __name__ == "__main__":
    main()
