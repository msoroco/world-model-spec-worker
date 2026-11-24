"""Freeze source-backed physical sample points without assigning legal labels."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove():
    landmarks_path = HERE / "judgment-grid-landmarks.json"
    zero_path = HERE / "zero-signal-boundary-proof.json"
    replay_path = HERE / "zero-exact-candidate-replay.json"
    landmarks = json.loads(landmarks_path.read_text())
    zero = json.loads(zero_path.read_text())
    replay = json.loads(replay_path.read_text())
    if landmarks["signal_lead_frames"] != [-1, 0, 1]:
        raise ValueError("Signal sample grid changed")
    if landmarks["gap_at_movement_m"] != [3.0, 8.0]:
        raise ValueError("Gap sample grid changed")
    if zero["signal_lead_frames"] != 0 or zero["source_frame_count"] != 900:
        raise ValueError("Zero signal source proof changed")
    runtime_manifest = HERE.parents[1] / "runtime" / "SOURCE-MANIFEST.json"
    if replay.get("runtime_manifest_sha256") != sha(runtime_manifest):
        raise ValueError("Zero exact candidate lacks current runtime binding")
    before = landmarks["points"]["left_signal_before_clear_gap"]
    late = landmarks["points"]["left_signal_late_clear_gap"]
    close = landmarks["points"]["left_signal_before_close_gap"]
    if not (before["departure_frame"] == late["departure_frame"] ==
            close["departure_frame"] == zero["first_body_departure_frame"]):
        raise ValueError("Departure frame differs across sample points")
    if not (before["nearest_target_body_gap_m"] ==
            late["nearest_target_body_gap_m"] == 8.0):
        raise ValueError("Signal sample target gap changed")
    if close["nearest_target_body_gap_m"] != 3.0:
        raise ValueError("Near gap sample changed")
    if close["signal_lead_frames"] != before["signal_lead_frames"]:
        raise ValueError("Gap sample signal stage changed")
    return {
        "format": "worker-c144550-physical-sweep-design",
        "source_proofs_sha256": {
            "judgment-grid-landmarks.json": sha(landmarks_path),
            "zero-signal-boundary-proof.json": sha(zero_path),
            "zero-exact-candidate-replay.json": sha(replay_path),
        },
        "signal": {
            "axis": "appropriate_signal_lead_frames",
            "unit": "original frames at 20 Hz",
            "range": [-1, 1],
            "spacing": 1,
            "selection_order": [-1, 1, 0],
            "source_case_ids": [late["case_id"], before["case_id"],
                                HERE.name + "__left_signal_at_departure_clear_gap"],
            "fixed_departure_frame": before["departure_frame"],
            "fixed_target_gap_m": 8.0,
            "measurement": "first complete original-body departure frame minus first appropriate original lamp frame",
            "interpretation": "physical sampling only; no statutory numeric lead time inferred",
        },
        "gap": {
            "axis": "nearest_target_body_gap_at_departure_m",
            "unit": "m",
            "range": [3.0, 8.0],
            "spacing": 5.0,
            "selection_order": [3.0, 8.0],
            "source_case_ids": [close["case_id"], before["case_id"]],
            "fixed_departure_frame": before["departure_frame"],
            "fixed_signal_lead_frames": 1,
            "measurement": "nearest original target-lane actor body gap along sourced lane heading at first complete-body departure",
            "interpretation": "physical sampling only; driver ascertainment and legal safety unresolved",
        },
        "selected_sweep_specs_complete": False,
        "selected_zero_case": False,
        "physical_acceptance_claimed": False,
        "legal_acceptance_claimed": False,
    }


if __name__ == "__main__":
    result = prove()
    (HERE / "physical-sweep-design.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"signal_points": result["signal"]["selection_order"],
                      "gap_points": result["gap"]["selection_order"]}, sort_keys=True))
