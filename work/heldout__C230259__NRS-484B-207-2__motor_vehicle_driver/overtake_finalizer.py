"""Derive saved overtaking observations only from retained originals."""

import argparse
import hashlib
import json
from pathlib import Path

from overtake_source import analyze, CAMERAS

CHANNELS = ("full_body_pass_gap_m", "ego_right_shift_m", "ego_speed_mps",
            "overtaker_lateral_offset_right_m", "notice_source_context",
            "right_pass_permission_context")


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(attempt, write_channels=True):
    root = Path(attempt)
    source = analyze(root)
    geometry = source["geometry"]
    samples = geometry["samples"]
    baseline = samples[0]["ego_right_projection_m"]
    streams = {name: [] for name in CHANNELS}
    for sample in samples:
        shared = {"frame": sample["frame"], "time_s": sample["time_s"]}
        values = {
            "full_body_pass_gap_m": sample["rear_to_front_gap_m"],
            "ego_right_shift_m": sample["ego_right_projection_m"] - baseline,
            "ego_speed_mps": sample["ego_speed_mps"],
            "overtaker_lateral_offset_right_m": sample["overtaker_lateral_offset_right_m"],
            "notice_source_context": {"driver_reference_camera": "driver_reference.mkv",
                                      "subjective_observation_confirmed": None,
                                      "subjective_hearing_confirmed": None},
            "right_pass_permission_context": {"site_source": "overtake_site_original.json",
                                               "permission_confirmed": None},
        }
        for name, value in values.items():
            streams[name].append(dict(shared, value=value))
    if write_channels:
        for name, rows in streams.items():
            path = root / (name + ".jsonl")
            if path.exists():
                raise ValueError("Derived overtaking channel already exists: " + name)
            path.write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))
    return {"format": "worker-analysis-report", "case_id": source["case_id"],
            "measurements": {name: {"method": "source-joined original overtaking geometry",
                                     "value": rows, "sources": source["source_sha256"]}
                             for name, rows in streams.items()},
            "completion_interval_s": geometry["completion_interval_s"],
            "max_precompletion_step_speed_increase_mps": geometry["max_precompletion_step_speed_increase_mps"],
            "completion_interval_speed_change_mps": geometry["completion_interval_speed_change_mps"],
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False,
            "limitations": source["limitations"]}


def native_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / "config.json").read_text())
    description = config["case"]["recording_description"]
    units = {channel["name"]: channel["unit"] for channel in description["channels"]}
    if set(units) != set(CHANNELS):
        raise ValueError("Exact overtaking recording description differs")
    evidence = []
    realized = {}
    for name in CHANNELS:
        path = root / (name + ".jsonl")
        rows = report["measurements"][name]["value"]
        evidence.append({"name": name, "unit": units[name], "reference": path.name,
                         "sha256": _hash(path)})
        realized[name] = {"unit": units[name], "method": "original 20 Hz source join",
                          "time_window": "all original overtaking frames", "statistic": "sample count",
                          "reference": path.name, "value": len(rows),
                          "sample_window_s": [rows[0]["time_s"], rows[-1]["time_s"]]}
    return {"case_id": report["case_id"], "measured_values": {name: len(report["measurements"][name]["value"]) for name in CHANNELS},
            "target_checks": [{"target": "two-vehicle overtaking path",
                               "requested": "measured full-body pass, rightward response and speed history",
                               "measured": len(report["measurements"]["full_body_pass_gap_m"]["value"]),
                               "method": "source-hashed original frame geometry",
                               "tolerance": None, "matched": False, "physical_cause_confirmed": False,
                               "cause_evidence": "Physical and perception review pending"}],
            "setup_confirmed": False, "behavior_attempted": True,
            "maneuver_completed": False,
            "termination_reason": "Original overtaking sources measured; outcome unverified",
            "physical_failure_flags": {"visibility_validated": False},
            "trace_reference": "trace.jsonl", "video_references": list(CAMERAS),
            "video_frame_map_reference": "video_frames.jsonl", "recording_description": description,
            "recording_evidence": evidence, "realized_observables": realized,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain prior overtaking analysis report")
    report = finalize(args.attempt)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    from worker_exchange.native_output import write_result
    write_result(args.attempt, native_result(args.attempt, report))


if __name__ == "__main__":
    main()
