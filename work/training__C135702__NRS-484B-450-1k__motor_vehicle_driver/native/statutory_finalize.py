"""Recorded-only obstruction measurement; never produces a legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from statutory_measure import measure
from source_join import VIEWS, check as check_source_join


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _video_frames(path: Path) -> int:
    call = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                           "-select_streams", "v:0", "-show_entries",
                           "stream=nb_read_frames", "-of",
                           "default=noprint_wrappers=1:nokey=1", str(path)],
                          capture_output=True, text=True, timeout=120)
    if call.returncode or not call.stdout.strip().isdigit():
        raise ValueError("Source video decode failed: " + path.name)
    return int(call.stdout.strip())


def exception_context_measurement(context: dict) -> dict:
    return {"exception_flags": context.get("exceptions"),
            "source_review": context.get("exception_source"),
            "legal_applicability_unresolved": True}


def obstruction_measurement(observed: dict) -> dict:
    return {"obstruction_kind": observed["obstruction_kind"],
            "parked_alongside_frames": observed["parked_alongside_frames"],
            "minimum_open_width_m": observed["minimum_open_width_m"],
            "physical_cause_confirmed": False}


def traffic_comparison_measurement(observed: dict) -> dict:
    return {"passing_body_width_m": observed["passing_body_width_m"],
            "passing_halt_frames": observed["passing_halt_frames"],
            "passing_crossed_obstruction_x": observed["passing_crossed_obstruction_x"],
            "minimum_passing_speed_m_s": observed["minimum_passing_speed_m_s"],
            "legal_verdict_claimed": False}


def finalize(attempt: Path, output: Path) -> dict:
    from worker_exchange.native_output import provenance_record, write_result

    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Choose fresh recorded-only processing outputs")
    cfg = json.loads(_required(attempt, "config.json").read_text())
    if (cfg.get("rate_hz"), cfg.get("frames"), cfg.get("duration_s")) != (20, 600, 30):
        raise ValueError("Original camera and duration contract differs")
    if cfg.get("case_id") not in cfg.get("supported_case_ids", [cfg.get("case_id")]):
        raise ValueError("Exact case not supported")
    provenance = provenance_record(attempt)
    original = provenance["provenance_kind"] == "native" and not provenance["diagnostic_fixture"]
    source_kind = "original_native" if original else "synthetic_cpu"
    names = ("native_samples.jsonl", "video_frames.jsonl", "camera-frames.jsonl",
             "exception-context.json", "obstruction-inventory.json", "road.xodr",
             "trace.jsonl", "capture/evidence.jsonl", "capture/native/frames.jsonl")
    hashes = {name: _sha(_required(attempt, name)) for name in names}
    joined = check_source_join(attempt, source_kind=source_kind)
    samples = _rows(attempt / "native_samples.jsonl")
    frames = _rows(attempt / "video_frames.jsonl")
    trace = _rows(attempt / "trace.jsonl")
    evidence = _rows(attempt / "capture/evidence.jsonl")
    if len(trace) != 600 or len(evidence) != 600:
        raise ValueError("Incomplete source Core/evidence frames")
    for index, (sample, mapping, core, sensor) in enumerate(zip(samples, frames, trace, evidence)):
        native = sample["native_frame"]
        if core.get("frame") != native or sensor.get("original_frame") != native:
            raise ValueError("Original Native/Core frame join differs")
        center = [(sample["ego_body_xy_m"][i] + sample["ego_body_xy_m"][i + 2]) / 2
                  for i in (0, 1)]
        if any(abs(core["position_m"][axis] - center[axis]) > .15 or
               abs(sensor["ego"]["position_m"][axis] - center[axis]) > .15
               for axis in (0, 1)):
            raise ValueError("Original Native/Core spatial join differs")
        if abs(core["speed_mps"] - sample["ego_speed_m_s"]) > .1:
            raise ValueError("Original Native/Core speed join differs")
        if mapping["video_frame"] != index:
            raise ValueError("Original video identity differs")
    context = json.loads((attempt / "exception-context.json").read_text())
    if context.get("case_id") != cfg["case_id"]:
        raise ValueError("Exact exception context case differs")
    if original:
        from runner import reviewed_context
        reviewed_context(attempt / "exception-context.json", cfg["case_id"])
        if any(row.get("context_sha256") != hashes["exception-context.json"] for row in samples):
            raise ValueError("Original exception context hash differs")
    else:
        if context.get("source_kind") != "synthetic_cpu":
            raise ValueError("Diagnostic exception provenance missing")
    inventory = json.loads((attempt / "obstruction-inventory.json").read_text())
    if inventory.get("obstruction_kind") != "physical_obstruction" or inventory.get("obstruction_xy_m") != samples[0]["obstruction_xy_m"]:
        raise ValueError("Original obstruction inventory differs")
    if original and inventory.get("source_kind") != "original_native":
        raise ValueError("Original physical obstruction inventory missing")
    observed = measure(attempt / "native_samples.jsonl", hashes["native_samples.jsonl"])
    video_counts = {view: _video_frames(_required(attempt, view + ".mkv")) for view in VIEWS}
    if set(video_counts.values()) != {600}:
        raise ValueError("Four original source videos have incomplete frame counts")
    channels = {name: [] for name in (
        "drv.standing_or_parked", "st.obstruction", "rel.bearing",
        "rel.centre_distance", "st.lane_width", "drv.hard_deceleration",
        "kin.velocity", "drv.forced_halt")}
    prior_passing_speed = None
    for row in samples:
        ego, obstacle = row["ego_body_xy_m"], row["obstruction_xy_m"]
        ego_center = ((ego[0] + ego[2]) / 2, (ego[1] + ego[3]) / 2)
        obstacle_center = ((obstacle[0] + obstacle[2]) / 2,
                           (obstacle[1] + obstacle[3]) / 2)
        dx, dy = obstacle_center[0] - ego_center[0], obstacle_center[1] - ego_center[1]
        current_speed = row["passing_speed_m_s"]
        values = {
            "drv.standing_or_parked": {"ego_speed_m_s": row["ego_speed_m_s"],
                                        "rest_observed": row["ego_speed_m_s"] <= .05,
                                        "activity_source": "operator_context_requires_review"},
            "st.obstruction": {"kind": row["obstruction_kind"], "body_xy_m": obstacle,
                               "barrier_actor_ids": row.get("barrier_actor_ids", [])},
            "rel.bearing": {"obstacle_bearing_deg": math.degrees(math.atan2(dy, dx)),
                              "reference": "ego_to_obstruction"},
            "rel.centre_distance": {"metres": math.hypot(dx, dy)},
            "st.lane_width": {"road_width_m": row["road_xy_m"][3] - row["road_xy_m"][1],
                              "sampled_clearance_m": row.get("controller_clearance_m")},
            "drv.hard_deceleration": {"passing_deceleration_m_s2": None if prior_passing_speed is None
                                      else (prior_passing_speed - current_speed) * 20,
                                      "hard_threshold_is_law": False},
            "kin.velocity": {"passing_speed_m_s": current_speed,
                              "ego_speed_m_s": row["ego_speed_m_s"]},
            "drv.forced_halt": {"traffic_conflict_source_flag": row["exceptions"]["traffic_conflict"],
                                "traffic_conflict_reviewed": row["exception_source"]["traffic_conflict_reviewed"],
                                "legal_necessity_unresolved": True},
        }
        for name, value in values.items():
            channels[name].append({"time_s": row["time_s"],
                                   "native_frame": row["native_frame"], "value": value})
        prior_passing_speed = current_speed
    channel_root = attempt / "channels"
    channel_root.mkdir(exist_ok=True)
    for name, rows in channels.items():
        (channel_root / (name + ".jsonl")).write_text("".join(
            json.dumps(row, allow_nan=False) + "\n" for row in rows))
    (channel_root / "exception_authority.json").write_text(
        json.dumps({"exception_authority": context}, indent=2) + "\n")
    result = {"case_id": cfg["case_id"], "measured_values": observed,
              "target_checks": [{"target": "traffic_opening_and_response",
                                 "requested": cfg["park_y_m"], "measured": observed,
                                 "method": "same-frame original body geometry and passing speed",
                                 "tolerance": "numeric engineering values only; no statutory cutoff",
                                 "matched": False, "physical_cause_confirmed": False,
                                 "cause_evidence": list(names)}],
              "setup_confirmed": original,
              "behavior_attempted": original,
              "maneuver_completed": original and observed["parked_alongside_frames"] >= 400,
              "termination_reason": "600 source frames retained",
              "physical_failure_flags": ["traffic_obstruction_causation_and_exceptions_require_review"],
              "trace_reference": "trace.jsonl",
              "video_references": [view + ".mkv" for view in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": cfg["recording_description"],
              "recording_evidence": [{"name": name, "unit": "structured",
                                       "reference": "channels/" + name + ".jsonl"}
                                      for name in channels] + [{"name": "exception_authority",
                                                                "unit": "structured",
                                                                "reference": "channels/exception_authority.json"}],
              "realized_observables": {"minimum_open_width_m": {
                  "value": observed["minimum_open_width_m"], "unit": "m",
                  "method": "sampled full-body rectangle free interval", "time_window": "600 frames",
                  "statistic": "minimum", "reference": "native_samples.jsonl"}},
              "provenance_kind": provenance["provenance_kind"],
              "diagnostic_fixture": provenance["diagnostic_fixture"],
              "accepted": False, "legal_verdict_claimed": False}
    write_result(attempt, result)
    measurements = {
        "source_exceptions": {"method": "exception_context_measurement",
                              "value": exception_context_measurement(context),
                              "sources": {name: hashes[name] for name in
                                          ("exception-context.json", "native_samples.jsonl")}},
        "source_obstruction": {"method": "obstruction_measurement",
                               "value": obstruction_measurement(observed),
                               "sources": {name: hashes[name] for name in
                                           ("native_samples.jsonl", "obstruction-inventory.json",
                                            "video_frames.jsonl", "camera-frames.jsonl")}},
        "source_traffic_response": {"method": "traffic_comparison_measurement",
                                    "value": traffic_comparison_measurement(observed),
                                    "sources": {name: hashes[name] for name in
                                                ("native_samples.jsonl", "video_frames.jsonl")}},
    }
    report = {"format": "c135702-obstruction-source-analysis-v1", "case_id": cfg["case_id"],
              "analysis_complete": True, "legal_verdict_claimed": False,
              "measurements": measurements,
              "source_join": joined, "source_sha256": hashes,
              "source_video_frames": video_counts, "provenance": provenance,
              "limitations": ["Diagnostic fixtures do not establish Native geometry or pixels.",
                              "Traffic obstruction, exception applicability and legal outcome require independent review."]}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
