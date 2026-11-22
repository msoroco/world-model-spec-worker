"""Source-bound saved finalizer for the C147332 red-X bus probes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lane_signal_measurement import measure
from source_review import validate as validate_site


CHANNELS = ("bus-body-history.jsonl", "lane-signal-history.jsonl", "camera-frame-map.jsonl")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError("original channel has no frames: " + path.name)
    return rows


def _recorded_sha(acquisition, name):
    value = acquisition.get(name)
    return value.get("sha256") if isinstance(value, dict) else value


def measure_activation(observed, site):
    return {"governed_lane_id": observed["governed_lane_id"],
            "governed_lane_bounds_m": observed["governed_lane_bounds_m"],
            "official_device_source_sha256": site["official_device_source_sha256"],
            "frame_count": len(observed["frame_observations"])}


def measure_entry(observed):
    return {"red_x_entry_frames": observed["red_x_entry_frames"],
            "frame_count": len(observed["frame_observations"])}


def measure_driving(observed):
    return {"red_x_driving_frames": observed["red_x_driving_frames"],
            "frame_count": len(observed["frame_observations"])}


def build_report(attempt):
    attempt = Path(attempt)
    acquisition = json.loads((attempt / "acquisition.json").read_text())
    site = validate_site(attempt / "reviewed-context.json", source_root=attempt)
    if _recorded_sha(acquisition, "reviewed-context.json") != _sha(attempt / "reviewed-context.json"):
        raise ValueError("site review packet is not bound to original acquisition")
    streams = []
    for name in CHANNELS:
        path = attempt / name
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
        digest = _sha(path)
        if _recorded_sha(acquisition, name) != digest:
            raise ValueError("original channel missing or changed: " + name)
        rows = _rows(path)
        verified_rows = []
        for row in rows:
            source_name = row.get("source_path")
            if (not isinstance(source_name, str) or not source_name or
                    Path(source_name).is_absolute() or ".." in Path(source_name).parts):
                raise ValueError("original channel row source path missing: " + name)
            source = attempt / source_name
            source_digest = _recorded_sha(acquisition, source_name)
            if (not source.is_file() or source_digest != _sha(source) or
                    (row.get("source_sha256") is not None and
                     row["source_sha256"] != source_digest)):
                raise ValueError("original channel row source missing or changed: " + name)
            verified_rows.append({**row, "source_sha256": source_digest})
        streams.append(verified_rows)
    if len({len(rows) for rows in streams}) != 1:
        raise ValueError("original channels have different frame counts")
    joined = []
    for body, signal, camera in zip(*streams):
        if signal.get("official_device_source_sha256") != site["official_device_source_sha256"]:
            raise ValueError("signal observation differs from reviewed device source")
        joined.append({"frame": body.get("frame"), "elapsed_seconds": body.get("elapsed_seconds"),
                       "body": body, "lane_signal": signal, "camera_frame": camera})
    observed = measure(joined)
    source_groups = {
        "red_x_activation_measurement": ("reviewed-context.json", "lane-signal-history.jsonl", "camera-frame-map.jsonl"),
        "red_x_entry_measurement": CHANNELS,
        "red_x_driving_measurement": CHANNELS,
    }
    methods = {"red_x_activation_measurement": ("measure_activation", measure_activation(observed, site)),
               "red_x_entry_measurement": ("measure_entry", measure_entry(observed)),
               "red_x_driving_measurement": ("measure_driving", measure_driving(observed))}
    measurements = {key: {"method": method, "value": value,
                          "sources": {name: _sha(attempt / name) for name in source_groups[key]}}
                    for key, (method, value) in methods.items()}
    return {"format": "worker-analysis-report", "analysis_complete": True,
            "site_review": site,
            "measurements": {"red_x_bus_lane": observed, **measurements},
            "source_hashes": {name: _recorded_sha(acquisition, name) for name in CHANNELS},
            "provenance_kind": "source_bound_original_or_diagnostic",
            "limitations": ["Authored red-X asset and route request do not establish actual rendered signal or bus motion.",
                            "Official-device and highway legal sufficiency require independent review."],
            "legal_verdict_claimed": False, "physical_acceptance_claimed": False}


def saved_result(attempt, report):
    """Create pinned Native result and converter channels from preserved originals."""
    from worker_exchange.native_output import physical_result, validate_result

    attempt = Path(attempt)
    scene = json.loads((attempt / "scene.json").read_text())
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    if (config.get("selected_case_id") != scene.get("case_id") or
            (config.get("law_id"), config.get("cell_id"), config.get("actor")) !=
            ("NRS-484B-307-12b", "C147332", "bus_driver") or
            config.get("case", {}).get("recording_description") != construction.get("recording_description")):
        raise ValueError("selected red-X case or recording contract changed")
    originals = [[json.loads(line) for line in (attempt / name).read_text().splitlines() if line.strip()]
                 for name in CHANNELS]
    channel_dir = attempt / "channels"
    channel_dir.mkdir(exist_ok=True)
    values = {
        "bus_full_body_footprint": [(row["elapsed_seconds"], row["bus_footprint"]) for row in originals[0]],
        "governed_lane_bounds": [(row["elapsed_seconds"], {"lane_id": row["governed_lane_id"],
            "bounds_m": row["lane_lateral_bounds_m"]}) for row in originals[1]],
        "overhead_red_x_state": [(row["elapsed_seconds"], {"symbol": row["symbol"],
            "faces_bus": row["faces_bus"],
            "official_device_source_sha256": row["official_device_source_sha256"]}) for row in originals[1]],
        "camera_frame_map": [(row["elapsed_seconds"], row["camera_names"]) for row in originals[2]],
    }
    description = construction["recording_description"]
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        if name not in values:
            raise ValueError("unimplemented declared red-X channel: " + name)
        target = channel_dir / (name + ".jsonl")
        with target.open("x") as stream:
            for time, value in values[name]:
                stream.write(json.dumps({"time_s": time, "value": value}, allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(target.relative_to(attempt))})
    context = channel_dir / "reviewed-context.json"
    context.write_text(json.dumps({"reviewed_highway_and_official_device": report["site_review"]},
                                  allow_nan=False) + "\n")
    evidence.append({"name": "reviewed_highway_and_official_device",
                     "unit": "retained original source packet",
                     "reference": str(context.relative_to(attempt))})
    observed = report["measurements"]["red_x_bus_lane"]
    suffix = scene["case_id"].rsplit("__", 1)[-1]
    if suffix in ("adjacent_travel", "lateral_entry"):
        target = "red-X lane entry"
        measured = bool(observed["red_x_entry_frames"])
        requested = suffix == "lateral_entry"
    elif suffix in ("red_lane_stand", "red_lane_drive"):
        target = "red-X lane driving"
        measured = bool(observed["red_x_driving_frames"])
        requested = suffix == "red_lane_drive"
    else:
        raise ValueError("unknown exact red-X case")
    result = {"case_id": scene["case_id"], "measured_values": observed,
              "target_checks": [{"target": target, "requested": requested,
                  "measured": measured, "method": "original bus footprint and signal frame-time join",
                  "tolerance": 0, "matched": measured == requested,
                  "physical_cause_confirmed": False,
                  "cause_evidence": report["source_hashes"]}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved original source and physical review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}}
    result = physical_result(attempt, result)
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build_report(args.attempt)
    result = saved_result(args.attempt, report)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    target = Path(args.attempt) / "result.json"
    if target.exists():
        raise ValueError("retain prior saved result; use a fresh analysis stage")
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
