"""Recorded-only C151707 analysis with independent survey and purpose sources.

The diagnostic records observable route facts. It makes no legal or physical
acceptance claim about a generated fixture or an unsurveyed Native attempt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from finalize_property import normalize

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
TERMS = ("dev.traffic_signal", "st.lane_enters", "st.driveway_or_alley_entrance",
         "kin.path_length", "rel.occupies", "st.intersection", "st.roadway", "kin.position")


def source(attempt: Path, relative: str) -> Path:
    path = attempt / relative
    if not path.is_file():
        raise ValueError("Missing required source: " + relative)
    return path


def read_rows(attempt: Path, relative: str) -> list[dict]:
    return [json.loads(line) for line in source(attempt, relative).read_text().splitlines()
            if line.strip()]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def join_originals(attempt: Path, native: list[dict], count: int) -> dict:
    trace = read_rows(attempt, "trace.jsonl")
    evidence = read_rows(attempt, "capture/evidence.jsonl")
    mapping = read_rows(attempt, "video_frames.jsonl")
    if any(len(rows) != count for rows in (native, trace, evidence, mapping)):
        raise ValueError("Original Native/capture/video source counts differ")
    previous = -1
    for index, (n, t, e, m) in enumerate(zip(native, trace, evidence, mapping)):
        frame = n.get("native_frame")
        time = n.get("t_s")
        if type(frame) is not int or frame <= previous or m.get("native_frame") != frame:
            raise ValueError("Original Native frame identity differs")
        if m.get("video_frame") != index or t.get("frame") != frame or e.get("original_frame") != frame:
            raise ValueError("Original capture frame join differs")
        if type(time) not in (int, float) or not math.isfinite(time):
            raise ValueError("Original Native time missing")
        if any(abs(float(value) - time) > 1e-4 for value in
               (m.get("time_s", -1), t.get("time_s", -1), e.get("recording_time_s", -1))):
            raise ValueError("Original capture timestamp join differs")
        body = n.get("body_vertices_xy_m", [])
        captured = e.get("ego", {}).get("body_vertices_m", [])
        if len(body) < 4 or len(captured) < 4:
            raise ValueError("Original body footprint missing")
        xy_native = {(round(float(p[0]), 4), round(float(p[1]), 4)) for p in body}
        xy_capture = {(round(float(p[0]), 4), round(float(p[1]), 4)) for p in captured}
        if xy_native != xy_capture:
            raise ValueError("Original capture body differs from Native body")
        previous = frame
    capture = json.loads(source(attempt, "capture/manifest.json").read_text())
    if capture.get("frames") != count or not capture.get("extraction_confirmed"):
        raise ValueError("Original capture extraction incomplete")
    return {name: sha(source(attempt, name)) for name in
            ("property-route-native.jsonl", "property-survey.json", "purpose-declaration.json",
             "trace.jsonl", "capture/evidence.jsonl", "capture/manifest.json", "video_frames.jsonl")}


def measure_property_route(attempt: Path, observed: dict) -> dict:
    names = ("property-route-native.jsonl", "property-survey.json", "purpose-declaration.json")
    value = {key: observed[key] for key in
             ("property_then_intersecting_street", "first_property_frame",
              "first_intersecting_street_frame", "steady_red_alone_before_property_entry",
              "steady_red_alone_at_property_entry", "cross_street_not_red_at_entry",
              "declared_purpose", "source_path_length_m")}
    return {"value": value, "method": "measure_property_route",
            "sources": {name: sha(source(attempt, name)) for name in names}}


def rebuild_channels(attempt: Path, native: list[dict], observed: dict, survey: dict) -> list[dict]:
    channel_dir = attempt / "channels"
    if channel_dir.exists() and any(channel_dir.iterdir()):
        raise ValueError("Derived channels must be rebuilt from original sources")
    channel_dir.mkdir(exist_ok=True)
    progress = []
    total = 0.0
    prior = None
    for row in native:
        xy = (float(row["x_m"]), float(row["y_m"]))
        if prior is not None:
            total += math.dist(prior, xy)
        progress.append(total)
        prior = xy
    if not math.isclose(total, observed["source_path_length_m"], abs_tol=1e-6):
        raise ValueError("Source path-length reduction differs")
    values = {
        "dev.traffic_signal": lambda r: {"approach_signal_actor_id": r["approach_signal_actor_id"],
             "native_state": r["approach_signal_native_state"],
             "lens_form": survey["approach_signal_lens_form"],
             "facing_source_id": survey["approach_signal_facing_source_id"]},
        "st.lane_enters": lambda r: survey["approach_lane_source"],
        "st.driveway_or_alley_entrance": lambda r: {"property_id": survey["property_id"],
             "boundary_source_id": survey["property_boundary_source_id"]},
        "kin.path_length": lambda r: progress[r["frame"]],
        "rel.occupies": lambda r: {"body_vertices_xy_m": r["body_vertices_xy_m"]},
        "st.intersection": lambda r: survey["cross_street_lane_source"],
        "st.roadway": lambda r: survey["cross_street_lane_source"],
        "kin.position": lambda r: [r["x_m"], r["y_m"]],
    }
    evidence = []
    for term in TERMS:
        relative = "channels/" + term + ".jsonl"
        data = "".join(json.dumps({"time_s": r["t_s"], "value": values[term](r)},
                                  allow_nan=False, sort_keys=True) + "\n" for r in native)
        (attempt / relative).write_text(data)
        evidence.append({"name": term, "unit": "structured", "reference": relative})
    contexts = (("property_survey", survey),
                ("controller_purpose", json.loads(source(attempt, "purpose-declaration.json").read_text())))
    for name, value in contexts:
        relative = "channels/" + name + ".json"
        (attempt / relative).write_text(json.dumps({name: value}, sort_keys=True) + "\n")
        evidence.append({"name": name, "unit": "structured", "reference": relative})
    return evidence


def finalize(attempt: Path, output: Path) -> dict:
    attempt, output = attempt.resolve(), output.resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Use a fresh attempt for immutable finalization")
    config = json.loads(source(attempt, "config.json").read_text())
    if config.get("rate_hz") != 20 or config.get("duration_s") != 30 or config.get("frames") != 600:
        raise ValueError("Exact 600-frame 20 Hz contract differs")
    native_path = source(attempt, "property-route-native.jsonl")
    survey_path = source(attempt, "property-survey.json")
    purpose_path = source(attempt, "purpose-declaration.json")
    native = read_rows(attempt, "property-route-native.jsonl")
    original_hashes = join_originals(attempt, native, 600)
    observed = normalize(native_path.read_bytes(), survey_path.read_bytes(), purpose_path.read_bytes())
    survey = json.loads(survey_path.read_text())
    measurement = measure_property_route(attempt, observed)
    recording = rebuild_channels(attempt, native, observed, survey)
    videos = [name + ".mkv" for name in VIEWS]
    for name in videos:
        source(attempt, name)
    property_route = config["case_id"].endswith("__probe_02")
    measured = observed["property_then_intersecting_street"]
    target = {"target": "observed route through property into cross street",
              "requested": property_route, "measured": measured,
              "method": "original Native body footprint against separately surveyed polygons",
              "tolerance": 0, "matched": measured is property_route,
              "physical_cause_confirmed": False,
              "cause_evidence": ["property-route-native.jsonl", "property-survey.json"]}
    diagnostic = observed["source_kind"] == "synthetic_native_sample"
    result = {"case_id": config["case_id"], "measured_values": observed,
              "target_checks": [target], "setup_confirmed": True,
              "behavior_attempted": True,
              "maneuver_completed": bool(observed["first_intersecting_street_frame"] is not None),
              "termination_reason": "full 600-frame original source retained",
              "physical_failure_flags": ["physical_property_authority_lens_facing_and_purpose_require_independent_review"],
              "trace_reference": "trace.jsonl", "video_references": videos,
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": recording,
              "realized_observables": {"observed_path_length_m": {
                  "value": observed["source_path_length_m"],
                  "unit": "m", "method": "sum of original Native position increments",
                  "time_window": "original 30 s", "statistic": "last",
                  "reference": "channels/kin.path_length.jsonl"}},
              "provenance_kind": "synthetic_fixture" if diagnostic else "native",
              "diagnostic_fixture": diagnostic, "accepted": False,
              "legal_verdict_claimed": False}
    report = {"format": "c151707-saved-property-analysis-v1", "case_id": config["case_id"],
              "measurements": {"property_bypass_observation": measurement},
              "original_joins": original_hashes,
              "scope": "saved synthetic CPU diagnostic" if diagnostic else
                       "recorded original source analysis; no legal or physical acceptance"}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (attempt / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
