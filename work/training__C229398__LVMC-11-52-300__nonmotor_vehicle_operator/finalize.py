"""Saved-only Native result projection for the nighttime parking duration case."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from duration_policy import TARGETS
from selected_measurement import measure


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_channels(attempt, config, episode):
    folder = attempt / "channels"
    folder.mkdir(exist_ok=False)
    names = [channel["name"] for channel in config["recording_description"]["channels"]]
    if set(names) != {"drv.standing_or_parked", "ru.motor_vehicle",
                      "ru.trailer_or_combination", "kin.time", "env.civil_time",
                      "drv.condition_in_effect", "st.roadway"}:
        raise ValueError("Night parking channel contract differs")
    context = json.loads((attempt / "review-source.json").read_text())["findings"]
    street = json.loads((attempt / "street-geometry.json").read_text())
    zone = ZoneInfo(context["civil_clock"]["iana_timezone"])
    streams = {name: (folder / (name + ".jsonl")).open("x") for name in names}
    try:
        with (attempt / "native-actor-frames.jsonl").open() as source:
            for index, line in enumerate(source):
                actor = json.loads(line)
                local = datetime.fromtimestamp((context["civil_clock"]["utc_start_ms"] +
                                                index * 50) / 1000, timezone.utc).astimezone(zone)
                values = {
                    "drv.standing_or_parked": {"reviewed_activity": context["parking_purpose"],
                                               "original_velocity_xyz_mps": actor[
                                                   "velocity_xyz_mps"]},
                    "ru.motor_vehicle": {"reviewed_self_propulsion": context[
                        "self_propulsion"], "reviewed_excluded_device": context["excluded_device"]},
                    "ru.trailer_or_combination": {"reviewed_transport_capability":
                                                   context["transport_capability"]},
                    "kin.time": {"utc_epoch_ms": context["civil_clock"][
                        "utc_start_ms"] + index * 50},
                    "env.civil_time": {"local_iso": local.isoformat(),
                                       "iana_timezone": zone.key},
                    "drv.condition_in_effect": 1 <= local.hour < 6,
                    "st.roadway": {"original_center_xyz_m": actor["center_xyz_m"],
                                   "street_bounds_xy_m": street["street_bounds_xy_m"],
                                   "reviewed_public_access": context["street_public_access"],
                                   "reviewed_city_limits": context["city_limits"]},
                }
                for name, stream in streams.items():
                    stream.write(json.dumps({"time_s": index / 20, "value": values[name]}) + "\n")
    finally:
        for stream in streams.values():
            stream.close()
    context_path = folder / "qualifying_source_review.json"
    context_path.write_text(json.dumps({"qualifying_source_review": {
        "packet_sha256": digest(attempt / "review-source.json"),
        "source_kind": episode["source_kind"],
        "review_supported": episode["review_supported"]}}, indent=2) + "\n")
    return ([{"name": name, "unit": "structured",
              "reference": "channels/" + name + ".jsonl"} for name in names] +
            [{"name": "qualifying_source_review", "unit": "structured",
              "reference": "channels/qualifying_source_review.json"}])


def finalize(attempt, output):
    from worker_exchange.native_output import write_result

    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    config["recording_description"] = construction["recording_description"]
    suffix = config["case_id"].rsplit("__", 1)[-1]
    if suffix not in TARGETS:
        raise ValueError("Unknown exact parking duration case")
    for name in ("trace.jsonl", "video_frames.jsonl", "raw.mkv"):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    episode = measure(attempt)
    source_kind = episode["source_kind"]
    synthetic = source_kind == "synthetic_cpu"
    requested_ms = round(TARGETS[suffix] * 1000)
    measured_ms = episode["longest_continuous_qualifying_ms"]
    within_one_frame = abs(measured_ms - requested_ms) <= 50
    sources = {name: digest(attempt / name) for name in
               ("trace.jsonl", "video_frames.jsonl", "raw.mkv")}
    sources.update(episode["sources"])
    complete = within_one_frame and episode["review_supported"]
    evidence = write_channels(attempt, config, episode)
    result = {
        "case_id": config["case_id"],
        "measured_values": {"longest_continuous_qualifying_ms": measured_ms,
                            "observed_over_thirty_minutes": episode[
                                "observed_over_thirty_minutes"]},
        "target_checks": [{"target": "night parking duration",
                           "requested": requested_ms, "measured": measured_ms,
                           "method": "source-joined 20 Hz original actor/civil-clock frames",
                           "tolerance": "50 ms one-frame engineering tolerance, not a legal threshold",
                           "matched": within_one_frame,
                           "physical_cause_confirmed": complete and not synthetic,
                           "cause_evidence": ["native-actor-frames.jsonl",
                                              "review-source.json", "street-geometry.json"]}],
        "setup_confirmed": episode["review_supported"],
        "behavior_attempted": True,
        "maneuver_completed": complete,
        "termination_reason": str(episode["frame_count"]) +
        " joined source frames; excerpt=" + str(episode["diagnostic_excerpt"]),
        "physical_failure_flags": [] if complete else ["duration_or_context_unverified"],
        "trace_reference": "trace.jsonl",
        "video_references": ["raw.mkv"],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config.get("recording_description", {}),
        "recording_evidence": evidence,
        "realized_observables": {"night_parking_duration_ms": {
            "value": measured_ms, "unit": "ms",
            "method": "longest source-qualified continuous interval",
            "time_window": ("diagnostic source excerpt" if episode["diagnostic_excerpt"]
                            else "complete 36063-frame night recording"),
            "statistic": "longest", "reference": "native-actor-frames.jsonl"}},
        "physical_checks": {"maneuver": {"status": "met" if complete else "not_met",
                                         "method": "source-joined parking duration",
                                         "sources": sources,
                                         "legal_verdict_claimed": False}},
        "provenance_kind": "synthetic_fixture" if synthetic else "original_native",
        "diagnostic_fixture": synthetic,
        "accepted": False,
        "legal_verdict_claimed": False,
    }
    write_result(attempt, result)
    report = {"format": "c229398-parking-analysis-v1",
              "case_id": config["case_id"], "analysis_complete": True,
              "measurements": {"night_parking_duration": {
                  "method": "finalize", "value": measured_ms,
                  "sources": {name: episode["sources"][name] for name in
                              ("native-actor-frames.jsonl", "review-source.json",
                               "street-geometry.json", "video_frames.jsonl")}},
                  "night_window_exception_context": {
                      "method": "finalize",
                      "value": {"source_review_supported": episode["review_supported"],
                                "first_utc_epoch_ms": episode["first_utc_epoch_ms"],
                                "last_utc_epoch_ms": episode["last_utc_epoch_ms"],
                                "classification_and_clock_require_original_review": synthetic,
                                "window_rule": "01:00 inclusive to 06:00 exclusive, local civil time"},
                      "sources": {name: episode["sources"][name] for name in
                                  ("review-source.json", "native-actor-frames.jsonl",
                                   "video_frames.jsonl")}}},
              "episode": episode, "source_hashes": sources,
              "provenance_kind": result["provenance_kind"],
              "diagnostic_excerpt": episode["diagnostic_excerpt"],
              "physical_or_legal_acceptance": False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))


if __name__ == "__main__":
    main()
