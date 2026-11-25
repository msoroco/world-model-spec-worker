"""Saved-only C376646 finalization from retained original source rows.

The output records observations. It never decides statutory inoperability,
cautiousness, right of way, or physical acceptance from CPU fixtures.
"""

import hashlib
import json
import shutil
from pathlib import Path

from inoperative_stop_measurements import analyze


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
BOUNDARY_FIELD = {
    "stop_line": "front_to_stop_line_signed_m",
    "crosswalk": "front_to_crosswalk_signed_m",
    "nearest_view": "front_to_nearest_view_signed_m",
}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_signal_states(report):
    return {"sample_count": len(report["samples"]),
            "ego_governing_off_all_frames": all(s["signal_state"] == "Off" for s in report["samples"]),
            "other_governing_off_all_frames": all(s["other_signal_state"] == "Off" for s in report["samples"]),
            "statutory_inoperability_judgment": "unresolved"}


def measure_stop_reference(report):
    return report["selected_stop_boundary"]


def measure_ego_full_halt(report):
    return report["ego_stopped_before_entry_observed"]


def measure_prior_stop(report):
    return report["other_completed_stop_before_ego_observed"]


def measure_intersection_occupancy(report):
    return {"other_inside_at_ego_entry": report["other_body_inside_at_ego_entry_observed"],
            "ego_entry": report["first_body_entry"]["ego"],
            "other_entry": report["first_body_entry"]["other"]}


def measure_post_stop_motion(report):
    halt = report["first_full_halt_before_or_at_selected_boundary"]["ego"]
    entry = report["first_body_entry"]["ego"]
    rows = [s for s in report["samples"] if halt and s["time_s"] > halt["time_s"] and
            (not entry or s["time_s"] <= entry["time_s"])]
    return {"halt_observed": halt is not None,
            "post_halt_through_entry_samples": [{"frame": s["frame"],
                                                   "time_s": s["time_s"],
                                                   "speed_mps": s["ego"]["speed_mps"]} for s in rows],
            "cautiousness_judgment": "unresolved"}


MEASUREMENTS = {
    "signal_states": measure_signal_states,
    "stop_reference": measure_stop_reference,
    "ego_full_halt": measure_ego_full_halt,
    "prior_stop": measure_prior_stop,
    "intersection_occupancy": measure_intersection_occupancy,
    "post_stop_motion": measure_post_stop_motion,
}


def finalize_saved(attempt, output):
    """Validate acquisition, derive channels, and write one fresh saved result."""
    from worker_exchange.native_output import physical_result, write_result

    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Retain prior finalization; choose a fresh saved version")
    required = ("config.json", "trace.jsonl", "vehicle_signal_history.jsonl",
                "video_frames.jsonl", "junction_context.json", "capture/evidence.jsonl",
                *(camera + ".mkv" for camera in CAMERAS))
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    cfg = json.loads((attempt / "config.json").read_text())
    if (cfg.get("cell_id") != "C376646" or cfg.get("law_id") != "NRS-484B-250-4" or
            not str(cfg.get("selected_case_id", "")).startswith("testing__C376646__NRS-484B-250-4__motor_vehicle_driver__")):
        raise ValueError("Wrong C376646 selected capture identity")
    description = cfg.get("recording_description")
    if not isinstance(description, dict) or not description.get("channels"):
        raise ValueError("Selected recording description required")
    report = analyze(attempt)
    history = _rows(attempt / "vehicle_signal_history.jsonl")
    mapping = _rows(attempt / "video_frames.jsonl")
    trace = _rows(attempt / "trace.jsonl")
    if (len(history) != len(mapping) or len(trace) != len(mapping) or
            any(t.get("frame") != m.get("carla_frame") or t.get("time_s") != m.get("time_s")
                for t, m in zip(trace, mapping))):
        raise ValueError("Original trace/video frame join failed")
    boundary = BOUNDARY_FIELD[report["selected_stop_boundary"]]
    values = {
        "ego_speed": ("m/s", lambda r: r["ego"]["speed_mps"]),
        "other_speed": ("m/s", lambda r: r["other"]["speed_mps"]),
        "ego_stop_boundary_distance": ("m", lambda r: r["ego"][boundary]),
        "signal_state": ("device state", lambda r: r["signal_state"]),
        "ego_position": ("m", lambda r: [sum(v[i] for v in r["ego"]["body_vertices_xy_m"]) /
                                          len(r["ego"]["body_vertices_xy_m"]) for i in (0, 1)]),
    }
    # Validate every derived value before creating any saved output.
    derived = {name: [value(row) for row in history] for name, (_, value) in values.items()}
    evidence_root = attempt / "evidence"
    evidence_root.mkdir(exist_ok=True)
    for name in ("trace.jsonl", "vehicle_signal_history.jsonl", "video_frames.jsonl",
                 "junction_context.json", "config.json"):
        shutil.copyfile(attempt / name, evidence_root / name)
    shutil.copytree(attempt / "capture", evidence_root / "capture", dirs_exist_ok=True)
    channels = attempt / "channels"
    channels.mkdir()
    evidence = []
    for name, (unit, _) in values.items():
        reference = "channels/" + name + ".jsonl"
        with (attempt / reference).open("x") as stream:
            for row, value in zip(history, derived[name]):
                stream.write(json.dumps({"time_s": row["time_s"], "original_frame": row["frame"],
                                         "value": value}, allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": unit, "reference": reference})
    evidence.append({"name": "junction_context", "unit": "structured record",
                     "reference": "junction_context.json"})
    checksums = {"evidence/" + p.relative_to(evidence_root).as_posix(): _sha(p)
                 for p in evidence_root.rglob("*") if p.is_file()}
    (attempt / "evidence-checksums.json").write_text(json.dumps(checksums, sort_keys=True) + "\n")
    result = {
        "case_id": cfg["selected_case_id"],
        "measured_values": {
            "selected_stop_boundary": report["selected_stop_boundary"],
            "first_full_halt": report["first_full_halt_before_or_at_selected_boundary"],
            "first_body_entry": report["first_body_entry"],
            "other_body_inside_at_ego_entry": report["other_body_inside_at_ego_entry_observed"],
        },
        "target_checks": [{"target": "ego_full_halt_before_entry", "requested": True,
                           "measured": report["ego_stopped_before_entry_observed"],
                           "method": "source-hashed complete-body stop and original frame entry order",
                           "tolerance": 0, "matched": report["ego_stopped_before_entry_observed"],
                           "physical_cause_confirmed": False,
                           "cause_evidence": list(report["sources"])}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False, "termination_reason": "Saved source assessment pending",
        "physical_failure_flags": ["Native signal visibility and legal judgments require original capture review"],
        "trace_reference": "trace.jsonl", "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl", "recording_description": description,
        "recording_evidence": evidence, "source_evidence_hashes": report["sources"],
        "capture_evidence_sha256": _sha(attempt / "capture/evidence.jsonl"),
        "realized_observables": {},
    }
    result = physical_result(attempt, result)
    write_result(attempt, result)
    measurements = {name: {"method": method.__name__, "value": method(report),
                           "sources": report["sources"]}
                    for name, method in MEASUREMENTS.items()}
    analysis = {"format": "worker-analysis-report",
                "case_id": cfg["selected_case_id"], "source_report": report,
                "source_hashes": report["sources"], "measurements": measurements,
                "physical_checks": result["physical_checks"],
                "realized_observables": result["realized_observables"],
                "provenance_kind": result["provenance_kind"],
                "diagnostic_fixture": result["diagnostic_fixture"],
                "limitations": ["Original signal states and motion require physical review; legal judgments unresolved"],
                "legal_verdict_asserted": False, "analysis_complete": True}
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + "\n")
    return analysis


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    finalize_saved(arguments.attempt, arguments.output)
