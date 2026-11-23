"""Read saved original channels and measure C147332 green-arrow coverage."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from green_lane_measurement import measure
from source_review import validate as validate_site


CHANNELS = ("bus-body-history.jsonl", "lane-signal-history.jsonl", "camera-frame-map.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def recorded_sha(acquisition, name):
    value = acquisition.get(name)
    return value.get("sha256") if isinstance(value, dict) else value


def source_rows(attempt, acquisition, name):
    path = attempt / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    if recorded_sha(acquisition, name) != sha(path):
        raise ValueError("original channel missing or changed: " + name)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(rows) < 2:
        raise ValueError("original channel needs at least two frames: " + name)
    verified = []
    for row in rows:
        rel = row.get("source_path")
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError("original channel row source path missing: " + name)
        source = attempt / rel
        digest = recorded_sha(acquisition, rel)
        if (not source.is_file() or sha(source) != digest or
                (row.get("source_sha256") is not None and row["source_sha256"] != digest)):
            raise ValueError("original channel row source missing or changed: " + name)
        verified.append(row)
    return verified


def verified_join(attempt):
    attempt = Path(attempt)
    acquisition = json.loads((attempt / "acquisition.json").read_text())
    packet = attempt / "reviewed-context.json"
    site = validate_site(packet, source_root=attempt)
    if recorded_sha(acquisition, packet.name) != sha(packet):
        raise ValueError("site review packet is not bound to original acquisition")
    streams = [source_rows(attempt, acquisition, name) for name in CHANNELS]
    if len({len(rows) for rows in streams}) != 1:
        raise ValueError("original channels have different frame counts")
    joined = []
    for body, signal, camera in zip(*streams):
        if (signal.get("official_device_source_sha256") != site["official_device_source_sha256"] or
                signal.get("highway_id") != site["highway_id"]):
            raise ValueError("signal observation differs from reviewed site")
        observed_green = {lane.get("lane_id") for lane in signal.get("lanes", [])
                          if lane.get("symbol") == "down_green_arrow"}
        if observed_green != set(site["governed_lane_ids"]):
            raise ValueError("observed green lanes differ from reviewed device")
        joined.append({"frame": body.get("frame"),
                       "elapsed_seconds": body.get("elapsed_seconds"),
                       "body": body, "lane_signals": signal, "camera_frame": camera})
    return joined, site


def build_report(attempt):
    attempt = Path(attempt)
    joined, site = verified_join(attempt)
    observed = measure(joined)
    sources = {name: sha(attempt / name) for name in CHANNELS}
    return {"format": "worker-analysis-report", "analysis_complete": True,
            "site_review": site,
            "measurements": {"green_arrow_bus_lane": observed,
                             "green_site_measurement": {"method": "measure_site",
                                "value": measure_site(site),
                                "sources": {"reviewed-context.json": sha(attempt / "reviewed-context.json"),
                                            "lane-signal-history.jsonl": sources["lane-signal-history.jsonl"]}},
                             "green_lane_coverage_measurement": {"method": "measure_lane_coverage",
                                "value": measure_lane_coverage(observed), "sources": sources},
                             "green_motion_measurement": {"method": "measure_bus_motion",
                                "value": measure_bus_motion(observed), "sources": sources}},
            "source_hashes": sources,
            "legal_verdict_claimed": False, "physical_acceptance_claimed": False,
            "limitations": ["Original camera frame mapping does not itself prove pixel visibility.",
                            "Official-device and highway legal sufficiency require independent review."]}


def measure_site(site):
    return {"highway_id": site["highway_id"],
            "highway_source_sha256": site["highway_source_sha256"],
            "official_device_source_sha256": site["official_device_source_sha256"],
            "governed_lane_ids": site["governed_lane_ids"]}


def measure_lane_coverage(observed):
    return {"permission_observed_frames": observed["permission_observed_frames"],
            "mapped_lane_bounds_m": observed["mapped_lane_bounds_m"],
            "frame_count": len(observed["frame_observations"])}


def measure_bus_motion(observed):
    return {"bus_moving_frames": observed["bus_moving_frames"],
            "frame_count": len(observed["frame_observations"])}


def saved_result(attempt, report):
    """Write converter channels from verified originals and a pinned Native result."""
    from worker_exchange.native_output import physical_result, validate_result

    attempt = Path(attempt)
    scene = json.loads((attempt / "scene.json").read_text())
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    if (config.get("selected_case_id") != scene.get("case_id") or
            (config.get("law_id"), config.get("cell_id"), config.get("actor")) !=
            ("NRS-484B-307-12a", "C147332", "bus_driver") or
            config.get("case", {}).get("recording_description") != construction.get("recording_description")):
        raise ValueError("selected green-arrow case or recording contract changed")
    kind = scene["case_id"].rsplit("__", 1)[-1]
    if kind not in ("green_selected_drive", "adjacent_dark_drive",
                    "second_green_drive", "green_selected_stand"):
        raise ValueError("unexpected exact green-arrow case")
    joined, _ = verified_join(attempt)
    observed = report["measurements"]["green_arrow_bus_lane"]
    expected_permission = kind != "adjacent_dark_drive"
    expected_motion = kind != "green_selected_stand"
    actual_permission = bool(observed["permission_observed_frames"])
    actual_motion = bool(observed["bus_moving_frames"])
    source_hashes = report["source_hashes"]
    checks = []
    for target, requested, measured in (
            ("full bus in lane governed by bus-facing downward green arrow",
             expected_permission, actual_permission),
            ("bus motion on original sampled frames", expected_motion, actual_motion)):
        checks.append({"target": target, "requested": requested,
                       "measured": measured, "method": "original body/signal/camera frame-time join",
                       "tolerance": 0, "matched": requested == measured,
                       "physical_cause_confirmed": False,
                       "cause_evidence": source_hashes})
    values = {
        "bus_full_body_footprint": [(row["elapsed_seconds"], row["body"]["bus_footprint"])
                                    for row in joined],
        "mapped_lane_signals": [(row["elapsed_seconds"], {
            "highway_id": row["lane_signals"]["highway_id"],
            "lanes": row["lane_signals"]["lanes"],
            "official_device_source_sha256": row["lane_signals"]["official_device_source_sha256"]})
                                for row in joined],
        "camera_frame_map": [(row["elapsed_seconds"], row["camera_frame"].get("camera_names", []))
                             for row in joined],
    }
    channel_dir = attempt / "channels"
    if channel_dir.exists():
        raise ValueError("retain prior converter channels; use a fresh analysis stage")
    channel_dir.mkdir()
    evidence = []
    description = construction["recording_description"]
    for channel in description["channels"]:
        name = channel["name"]
        if name not in values:
            raise ValueError("unimplemented declared green-arrow channel: " + name)
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
    result = {"case_id": scene["case_id"], "measured_values": observed,
              "target_checks": checks, "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
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
    output = Path(args.output)
    if output.exists():
        raise ValueError("retain prior report; choose a fresh output")
    target = Path(args.attempt) / "result.json"
    if target.exists():
        raise ValueError("retain prior saved result; use a fresh analysis stage")
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
