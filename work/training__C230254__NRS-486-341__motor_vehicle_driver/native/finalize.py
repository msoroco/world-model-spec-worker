"""Runtime saved-only analyzer for original NRS 486.341 acquisition."""

import argparse
import hashlib
import json
from pathlib import Path

from finalize_lane_use import finalize_bound
from physical_audit import assess


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def lane_use_geometry(attempt, values, bound):
    return {"method": "lane_use_geometry", "value": values,
            "sources": {name: bound["sources"][name] for name in
                        ("lane-use-source.jsonl", "video_frames.jsonl")}}


def chapter_486_context(attempt, bound):
    path = Path(attempt) / "road-authority.json"
    if not path.is_file():
        raise ValueError("Missing required source: road-authority.json")
    survey = json.loads((Path(attempt) / "lane-use-context.json").read_text())
    return {"method": "chapter_486_context",
            "value": {"map_name": survey["map_name"],
                      "source_review_pending": True,
                      "protected_classification_claimed": False},
            "sources": {"lane-use-context.json": bound["sources"]["lane-use-context.json"],
                        "road-authority.json": hashlib.sha256(path.read_bytes()).hexdigest()}}


def finalize(attempt, output):
    # The runtime sets its output root before launching this entrypoint. Keep
    # direct runtime imports inside the function and after source validation.
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain original and prior analysis results")
    config_path = attempt / "config.json"
    if not config_path.is_file():
        raise ValueError("Missing required source: config.json")
    config = json.loads(config_path.read_text())
    if config.get("rate_hz") != 20 or config.get("frames") != 600:
        raise ValueError("Exact full-window capture contract changed")
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    measured_path = attempt / "lane-use-measured.jsonl"
    bound = finalize_bound(attempt, measured_path)
    if bound["measured_frames"] != 600:
        raise ValueError("Original geometry does not cover all 600 frames")
    measurements = [json.loads(line) for line in measured_path.read_text().splitlines()]
    channel_path = channels / "lane-use-original-geometry.jsonl"
    channel_path.write_text("".join(json.dumps({"time_s": row["time_s"], "value": row},
                                               allow_nan=False) + "\n" for row in measurements))
    frames = [json.loads(line) for line in
              (attempt / "video_frames.jsonl").read_text().splitlines() if line.strip()]
    camera_channel = channels / "four-camera-video.jsonl"
    camera_channel.write_text("".join(json.dumps({
        "time_s": frame["time_s"], "value": frame["camera_native_frames"]},
        allow_nan=False) + "\n" for frame in frames))
    context_channel = channels / "chapter-486-context.json"
    context_channel.write_text(json.dumps({"chapter_486_context":
        chapter_486_context(attempt, bound)["value"]}, allow_nan=False) + "\n")
    motion = assess(attempt)
    from worker_exchange.native_output import physical_result, provenance_record, write_result
    provenance = provenance_record(attempt)
    native = provenance["provenance_kind"] == "native" and not provenance["diagnostic_fixture"]
    overlap = [row["ego_lane_overlap_fraction"] for row in measurements]
    gaps = [row["footprint_surface_gap_m"] for row in measurements]
    values = {"frame_count": len(measurements),
              "ego_lane_overlap_range": [min(overlap), max(overlap)],
              "surface_gap_range_m": [min(gaps), max(gaps)],
              "original_motion_status": motion["status"]}
    result = {
        "case_id": config["case_id"],
        "measured_values": values,
        "target_checks": [{
            "target": "actual subject manner relative to protected motorcycle full lane use",
            "requested": {"setting": config["requested_setting"]},
            "measured": values,
            "method": "original actor bounding boxes and mapped lane geometry across synchronized frames",
            "tolerance": "none; no statutory clearance cutoff exists in supplied text",
            "matched": False,
            "physical_cause_confirmed": False,
            "cause_evidence": ["lane-use-source.jsonl", "video_frames.jsonl",
                               "lane-use-context.json", "channels/lane-use-original-geometry.jsonl"]}],
        "setup_confirmed": False,
        "behavior_attempted": native,
        "maneuver_completed": False,
        "termination_reason": "Saved geometry measured; physical and legal review pending",
        "physical_failure_flags": ["actual_full_lane_use_requires_independent_review",
                                   "chapter_486_classification_requires_source_review",
                                   "camera_visibility_unverified"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in VIEWS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": [{"name": "lane_use_original_geometry", "unit": "structured",
                                "reference": "channels/lane-use-original-geometry.jsonl"},
                               {"name": "four_camera_video", "unit": "structured",
                                "reference": "channels/four-camera-video.jsonl"},
                               {"name": "chapter_486_context", "unit": "structured",
                                "reference": "channels/chapter-486-context.json"}],
        "realized_observables": {"ego_lane_overlap_fraction": {
            "value": max(overlap), "unit": "fraction", "statistic": "maximum",
            "method": "source-bound full footprint/lane polygon intersection",
            "time_window": "600 original frames",
            "reference": "channels/lane-use-original-geometry.jsonl"}},
        "accepted": False,
        "legal_verdict_claimed": False,
    }
    result = physical_result(attempt, result)
    write_result(attempt, result)
    report = {"format": "worker-nrs486-341-lane-use-analysis-v1",
              "case_id": config["case_id"], "analysis_complete": True,
              "measurements": {"lane_use_geometry": lane_use_geometry(attempt, values, bound),
                               "chapter_486_context": chapter_486_context(attempt, bound)},
              "independent_motion_check": motion,
              "provenance_kind": provenance["provenance_kind"],
              "diagnostic_fixture": provenance["diagnostic_fixture"],
              "legal_verdict_claimed": False,
              "limitations": ["Chapter 486 classification and highway context need original-source review.",
                              "Full use and deprivation have no numeric legal cutoff in supplied law.",
                              "Actual camera pixels and physical interaction need independent review."]}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
