"""Saved-only source projection of signed roadway riding; no legal verdict."""

import argparse
import hashlib
import json
from pathlib import Path

from signed_access_measure import CAMERAS, FRAME_COUNT, derive


CHANNELS = ("dev.regulatory_sign", "dev.governs", "dev.position", "ru.bicycle",
            "ru.electric_bicycle", "ru.electric_scooter", "st.sidewalk",
            "st.roadway", "rel.occupies")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(attempt, output):
    from worker_exchange.native_output import write_result

    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    config["recording_description"] = construction["recording_description"]
    for name in ("trace.jsonl", "video_frames.jsonl", "raw.mkv", "setup.json", "raw-frames.json"):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    measured = derive(attempt)
    setup = json.loads((attempt / "setup.json").read_text())
    frames = json.loads((attempt / "raw-frames.json").read_text())
    if setup.get("case_id") != config["case_id"]:
        raise ValueError("Sign review belongs to another exact case")
    channel_names = [row["name"] for row in config["recording_description"]["channels"]]
    if set(channel_names) != set(CHANNELS):
        raise ValueError("Signed-road recording channels differ")
    folder = attempt / "channels"
    folder.mkdir(exist_ok=False)
    streams = {name: (folder / (name + ".jsonl")).open("x") for name in CHANNELS}
    try:
        for frame in frames:
            x = frame["actor_x_m"]
            inside = setup["governed_x_interval_m"][0] <= x <= setup["governed_x_interval_m"][1]
            values = {
                "dev.regulatory_sign": {"erected": setup["prohibition_sign_erected"],
                                        "message": setup.get("sign_text")},
                "dev.governs": {"roadway_interval_x_m": setup["governed_x_interval_m"],
                                "actor_in_interval": inside},
                "dev.position": setup.get("sign_position_xyz_m", [40, -3.5, 2]),
                "ru.bicycle": setup["actor_kind"] == "bicycle",
                "ru.electric_bicycle": setup["actor_kind"] == "electric_bicycle",
                "ru.electric_scooter": setup["actor_kind"] == "electric_scooter",
                "st.sidewalk": False,
                "st.roadway": {"ridden": frame["riding_machine"], "x_m": x,
                               "surface": setup["surface_kind"]},
                "rel.occupies": {"actor_on_signed_roadway": inside},
            }
            for name, stream in streams.items():
                stream.write(json.dumps({"time_s": frame["elapsed_s"],
                                         "value": values[name]}) + "\n")
    finally:
        for stream in streams.values():
            stream.close()
    (folder / "sign_source_review.json").write_text(json.dumps({
        "sign_source_review": {"setup_sha256": digest(attempt / "setup.json"),
                               "original_review": measured["source_kind"] == "original_native_review",
                               "sign_pixels_verified": measured["sign_pixels_verified"],
                               "administrative_authority_verified": measured[
                                   "administrative_authority_verified"]}}, indent=2) + "\n")
    evidence = [{"name": name, "unit": "structured",
                 "reference": "channels/" + name + ".jsonl"} for name in CHANNELS]
    evidence.append({"name": "sign_source_review", "unit": "structured",
                     "reference": "channels/sign_source_review.json"})
    complete = measured["riding_frames"] == FRAME_COUNT and measured[
        "source_kind"] == "original_native_review"
    hashes = {name: digest(attempt / name) for name in
              ("setup.json", "raw-frames.json", "video_frames.jsonl", "trace.jsonl", "raw.mkv")}
    result = {"case_id": config["case_id"],
              "measured_values": {"ridden_signed_roadway_frames": measured[
                  "inside_governed_segment_frames"]},
              "target_checks": [{"target": "signed roadway riding position",
                                 "requested": config["route_kind"],
                                 "measured": measured["inside_governed_segment_frames"],
                                 "method": "source joined original rider, roadway and sign interval",
                                 "tolerance": "exact frame join; no legal spatial tolerance inferred",
                                 "matched": complete,
                                 "physical_cause_confirmed": complete and
                                 measured["sign_pixels_verified"],
                                 "cause_evidence": ["setup.json", "raw-frames.json",
                                                    "video_frames.jsonl"]}],
              "setup_confirmed": measured["sign_pixels_verified"],
              "behavior_attempted": True, "maneuver_completed": complete,
              "termination_reason": str(measured["riding_frames"]) + " source joined frames",
              "physical_failure_flags": [] if complete else ["original_sign_or_riding_unverified"],
              "trace_reference": "trace.jsonl", "video_references": ["raw.mkv"],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": evidence,
              "realized_observables": {"signed_roadway_riding_frames": {
                  "value": measured["inside_governed_segment_frames"], "unit": "frames",
                  "method": "source-joined sign-governed interval and rider pose",
                  "time_window": "all observed frames", "statistic": "count",
                  "reference": "raw-frames.json"}},
              "physical_checks": {"maneuver": {"status": "met" if complete else "unverified",
                                               "method": "original sign and rider source join",
                                               "sources": hashes,
                                               "legal_verdict_claimed": False}},
              "provenance_kind": "original_native" if complete else "synthetic_fixture",
              "diagnostic_fixture": not complete, "accepted": False,
              "legal_verdict_claimed": False}
    write_result(attempt, result)
    report = {"format": "c230207-signed-access-analysis-v1",
              "case_id": config["case_id"], "analysis_complete": True,
              "measurements": {"signed_roadway_riding": {
                  "method": "finalize", "value": measured["inside_governed_segment_frames"],
                  "sources": {name: hashes[name] for name in
                              ("setup.json", "raw-frames.json", "video_frames.jsonl")}}},
              "source_measurement": measured, "source_hashes": hashes,
              "diagnostic_excerpt": measured["diagnostic_excerpt"],
              "physical_or_legal_acceptance": False}
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    print(json.dumps(finalize(arguments.attempt, arguments.output)))


if __name__ == "__main__":
    main()
