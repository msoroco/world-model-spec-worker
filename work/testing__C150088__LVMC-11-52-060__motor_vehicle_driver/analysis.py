"""Saved-only projection measurement from sealed Native or explicit CPU fixture.

An engineering target and the statutory fifteen-foot boundary remain distinct.
The report never supplies a legal finding or claims pixel-level visibility.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from projection_capture import CAMERAS, FRAMES
from projection_construction import CASES
from projection_measurement import ASSIGNMENT, LIMIT_M, measure_packet
from projection_sources import load_reviewed, sha


def required(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def measure_projection(measurements):
    maxima = [item["maximum_street_projection_m"] for item in measurements]
    controlling = max(measurements, key=lambda item: item["maximum_street_projection_m"])
    category = max(controlling["parts"],
                   key=lambda part: part["maximum_street_projection_m"])["category"]
    return {"maximum_m": max(maxima), "minimum_m": min(maxima),
            "controlling_part": category, "statutory_boundary_m": LIMIT_M}


def verify_sources(root, case_id):
    seal_path = root / "capture-seal.json"
    if seal_path.is_file():
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
        if (seal.get("format") != "worker-sealed-capture" or
                seal.get("provenance_kind") != "native" or
                seal.get("diagnostic_fixture") is not False or
                seal.get("frames") != FRAMES or
                seal.get("restoration", {}).get("restored") is not True):
            raise ValueError("sealed original Native projection capture required")
        sources = seal.get("sources")
        mandatory = {"original-projection-history.jsonl", "camera-frame-map.jsonl",
                     "video_frames.jsonl", "trace.jsonl", "reviewed-site.json",
                     "reviewed-packet/reviewed-site.json",
                     *{name + ".mkv" for name in CAMERAS}}
        if not isinstance(sources, dict) or not mandatory <= set(sources):
            raise ValueError("original projection source inventory incomplete")
        for name, digest in sources.items():
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts or sha(required(root, name)) != digest:
                raise ValueError("sealed original source changed: " + name)
        revision = seal.get("native_revision", {})
        if (revision.get("construction_sha256") != sha(required(root, "construction.json")) or
                revision.get("runner_sha256") != sha(required(root, "runner.py"))):
            raise ValueError("sealed Native implementation changed")
        _, reviewed_site = load_reviewed(root / "reviewed-packet" / "reviewed-site.json", case_id)
        saved_site = json.loads(required(root, "reviewed-site.json").read_text(encoding="utf-8"))
        if saved_site != reviewed_site:
            raise ValueError("original reviewed curb/site source differs")
        retained_packet = json.loads(required(root, "reviewed-packet/reviewed-site.json").read_text(encoding="utf-8"))
        from projection_sources import validate_native_adapter
        validate_native_adapter(retained_packet, required(root, "reviewed-packet/native-adapter.py"))
        return False, {"capture-seal.json": sha(seal_path),
                       "original-projection-history.jsonl": sha(required(root, "original-projection-history.jsonl"))}
    note = json.loads(required(root, "diagnostic-source-note.json").read_text(encoding="utf-8"))
    if (note.get("source_kind") != "synthetic_diagnostic_fixture" or
            note.get("accepted_original_source") is not False or
            note.get("case_id") != case_id):
        raise ValueError("explicit synthetic projection diagnostic provenance required")
    return True, {"diagnostic-source-note.json": sha(root / "diagnostic-source-note.json"),
                  "original-projection-history.jsonl": sha(required(root, "original-projection-history.jsonl"))}


def analyze(root):
    root = Path(root)
    config = json.loads(required(root, "config.json").read_text(encoding="utf-8"))
    case_id = config.get("selected_case_id")
    case = next((item for item in CASES if item.case_id == case_id), None)
    if config.get("assignment_id") != ASSIGNMENT or case is None:
        raise ValueError("saved exact projection assignment differs")
    diagnostic, source = verify_sources(root, case_id)
    history = rows(required(root, "original-projection-history.jsonl"))
    cameras = rows(required(root, "camera-frame-map.jsonl"))
    frame_map = rows(required(root, "video_frames.jsonl"))
    trace = rows(required(root, "trace.jsonl"))
    expected_frames = FRAMES if not diagnostic else len(history)
    if (expected_frames < (FRAMES if not diagnostic else 9) or
            not all(len(part) == expected_frames for part in (history, cameras, frame_map, trace))):
        raise ValueError("complete source and camera history required")
    measurements = []
    previous = None
    first_time = history[0].get("time_s")
    if type(first_time) not in (float, int):
        raise ValueError("original projection start time missing")
    for index, (record, camera, video, graph) in enumerate(zip(history, cameras, frame_map, trace)):
        frame = record.get("frame")
        if (type(frame) is not int or (previous is not None and frame != previous + 1) or
                camera.get("frame_index") != index or camera.get("native_frame") != frame or
                camera.get("camera_frames") != {name: frame for name in CAMERAS} or
                video.get("video_frame") != index or video.get("carla_frame") != frame or
                video.get("native_frame") != frame or graph.get("frame") != frame or
                abs(record.get("time_s", -1) - first_time - index / 20) > .002 or
                abs(camera.get("time_s", -1) - record["time_s"]) > .002 or
                abs(video.get("time_s", -1) - record["time_s"]) > .002):
            raise ValueError("original projection/frame/camera join differs")
        previous = frame
        if record.get("case_id") != case_id:
            raise ValueError("original projection case differs")
        packet = dict(record, load_present=case.controlling_part == "load",
                      trailer_attached=case.controlling_part == "trailer")
        measurements.append(measure_packet(packet, source))
    summary = measure_projection(measurements)
    maximum, minimum = summary["maximum_m"], summary["minimum_m"]
    if maximum - minimum > .10:
        raise ValueError("parked assembly projection drift exceeds engineering stability tolerance")
    # A target match is an engineering observation, never a legal conclusion.
    target_matched = abs(maximum - case.projection_m) <= .08
    boundary_uncertain = minimum - .02 <= LIMIT_M <= maximum + .02
    source = {**source, "video_frames.jsonl": sha(root / "video_frames.jsonl"),
              "camera-frame-map.jsonl": sha(root / "camera-frame-map.jsonl")}
    channels = {
        "maximum_perpendicular_projection": lambda m, row: m["maximum_street_projection_m"],
        "controlling_physical_part": lambda m, row: max(
            m["parts"], key=lambda part: part["maximum_street_projection_m"])["category"],
        "curb_street_side_geometry": lambda m, row: {
            "curb_segment_start_m": row["curb_segment_start_m"],
            "curb_segment_end_m": row["curb_segment_end_m"],
            "street_side_reference_m": row["street_side_reference_m"]},
        "parked_assembly_stability": lambda m, row: maximum - minimum,
        "camera_frame_identity": lambda m, row: row["frame"],
    }
    evidence = []
    for channel in config["case"]["recording_description"]["channels"]:
        name = channel["name"]
        if name not in channels:
            raise ValueError("unknown projection recording channel: " + name)
        target = root / ("channel-" + name + ".jsonl")
        target.write_text("".join(json.dumps({"time_s": row["time_s"],
            "value": channels[name](measurement, row)}) + "\n"
            for row, measurement in zip(history, measurements)), encoding="utf-8")
        evidence.append({"name": name, "unit": channel["unit"], "reference": target.name})
    for context in config["case"]["recording_description"]["context_inputs"]:
        name = context["name"]
        if name == "reviewed_original_opendrive_and_curb_survey":
            value = {"source": "diagnostic-source-note.json" if diagnostic else "reviewed-packet/reviewed-site.json",
                     "source_sha256": source.get("diagnostic-source-note.json") if diagnostic else source.get("capture-seal.json"),
                     "diagnostic_fixture": diagnostic}
        elif name == "vehicle_load_trailer_attachment":
            value = {"controlling_part": summary["controlling_part"],
                     "original_history_sha256": source["original-projection-history.jsonl"],
                     "diagnostic_fixture": diagnostic}
        else:
            raise ValueError("unknown projection context: " + name)
        target = root / ("context-" + name + ".json")
        target.write_text(json.dumps({name: value}, sort_keys=True) + "\n", encoding="utf-8")
        evidence.append({"name": name, "unit": context["unit"], "reference": target.name})
    from worker_exchange.native_output import write_result
    status = "unverified" if diagnostic else ("met" if target_matched else "not_met")
    physical = {key: {"status": status if key == "target" else "unverified",
                      "method": "source-bound complete part and curb geometry; original pixels require review",
                      "sources": source, "intervals": [{"first_frame": history[0]["frame"],
                                                       "last_frame": history[-1]["frame"]}],
                      "legal_verdict_claimed": False}
                for key in ("setup", "target", "maneuver")}
    result = {"case_id": case_id,
              "measured_values": {"maximum_perpendicular_projection_m": maximum,
                                  "minimum_during_dwell_m": minimum,
                                  "controlling_part": summary["controlling_part"]},
              "target_checks": [{"target": "original complete assembly perpendicular projection",
                                 "requested": case.projection_m, "measured": maximum,
                                 "method": "original curb normal and all complete physical part outlines",
                                 "tolerance": .08, "matched": target_matched,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": source}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "parked assembly measured; physical visibility pending independent review",
              "physical_failure_flags": [] if not diagnostic else ["original_native_capture_absent"],
              "physical_checks": physical, "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["case"]["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "diagnostic_fixture": diagnostic, "physical_acceptance_claimed": False,
              "legal_verdict_claimed": False}
    write_result(root, result)
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "analysis_complete": True, "diagnostic_fixture": diagnostic,
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
              "measurements": {"maximum_perpendicular_projection": {
                  "value": {**summary, "boundary_uncertain": boundary_uncertain},
                  "unit": "m", "method": "measure_projection",
                  "sources": source}},
              "target_check": {"requested_m": case.projection_m, "measured_m": maximum,
                               "construction_tolerance_m": .08, "matched": target_matched,
                               "legal_equality_claimed": False},
              "limitations": ["Curb and street-side survey require local review.",
                              "At-boundary observations retain measurement uncertainty.",
                              "CPU fixtures cannot establish original physical pixels or legal acceptance."]}
    if diagnostic:
        report["limitations"].append("Synthetic diagnostic source; no Native physical finding.")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior projection analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n", encoding="utf-8")
