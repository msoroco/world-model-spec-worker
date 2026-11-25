"""Finalize sealed original C111610 capture without issuing a legal verdict.

The selected analyzer is intentionally strict about source identity. A synthetic
diagnostic can exercise the software path but never establish Native provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from saved_delivery import join
import crosswalk


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def required(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def source(root):
    capture = root / "capture"
    if not capture.is_dir():
        raise ValueError("Missing required source: capture/source-index.json")
    index = read(required(capture, "source-index.json"))
    diagnostic = index.get("format") == "c111610-diagnostic-source-index-v1"
    if index.get("format") not in ("c111610-native-source-index-v1",
                                   "c111610-diagnostic-source-index-v1"):
        raise ValueError("Original capture index differs")
    files = {}
    for name in ("site", "ego", "pedestrian", "exception_review", "frame_map", "camera_manifest"):
        item = index.get("files", {}).get(name)
        expected_source = "diagnostic_synthetic" if diagnostic else "native_original"
        if not isinstance(item, dict) or item.get("source") != expected_source:
            raise ValueError("Original source index missing: " + name)
        if not (capture / item["path"]).is_file():
            raise ValueError("Missing required source: capture/" + item["path"])
        path = required(capture, item["path"])
        if path.resolve().parent != capture.resolve() or digest(path) != item.get("sha256"):
            raise ValueError("Original source hash differs: " + name)
        files[name] = read(path)
    if index.get("case_id") != read(required(root, "scene.json"))["case_id"]:
        raise ValueError("Original capture case differs")
    return capture, index, files


def diagnostic_measurement(root, scene, index, files):
    """Exercise saved measurements on labelled synthetic sources, without pixels."""
    site = crosswalk.bind_site(files["site"], index["map_name"], scene["turn_direction"])
    observations = []
    clocks = files["frame_map"]
    for i, (driver, person, clock) in enumerate(zip(files["ego"], files["pedestrian"], clocks)):
        if any(row["native_frame"] != clock["native_frame"] for row in (driver, person)):
            raise ValueError("Diagnostic actor/frame source differs")
        observations.append(crosswalk.measure_frame(site, i,
            dict(driver, source_ref="diagnostic:ego:" + str(i)),
            dict(person, source_ref="diagnostic:pedestrian:" + str(i)),
            files["exception_review"]))
    if not observations or len(observations) != len(clocks):
        raise ValueError("Diagnostic source frame count differs")
    conditions = {row["device_condition"] for row in observations}
    if conditions != {scene["official_device_condition"]}:
        raise ValueError("Diagnostic exact device case differs")
    measurement = {"measurements": observations,
                   "summary": {"measured_device_condition": next(iter(conditions)),
                               "crosswalk_and_destination_half_frames": sum(
                                   row["pedestrian_in_crosswalk"] and
                                   row["pedestrian_on_destination_half"]
                                   for row in observations),
                               "ego_brake_frames": sum(row["ego_brake"] for row in observations)},
                   "frame_count": len(observations)}
    write(root / "saved-delivery-join-measurement.json", measurement)
    return measurement


def encode_saved_views(root, capture):
    """Encode the four retained PNG sequences, never modifying acquisition."""
    for name in VIEWS:
        target = root / (name + ".mkv")
        if target.exists():
            continue
        pattern = capture / "original-frames" / (name + "-%06d.png")
        if not (capture / "original-frames" / (name + "-000000.png")).is_file():
            raise ValueError("Missing required source: original-frames/" + name)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "20",
                        "-i", str(pattern), "-frames:v", "600", "-c:v", "ffv1",
                        str(target)], check=True, timeout=600)


def measure_device(files, measurement):
    return measurement["summary"]["measured_device_condition"]


def measure_geometry(files, measurement):
    site = files["site"]
    return {"crosswalk": site["crosswalk"],
            "lane_inventory": site["lanes"]}


def measure_destination(files, measurement):
    return measurement["summary"]["crosswalk_and_destination_half_frames"]


def measure_opposite(files, measurement):
    rows = [row for row in measurement["measurements"]
            if row["pedestrian_in_crosswalk"] and
            not row["pedestrian_on_destination_half"]]
    return {"opposite_crosswalk_frames": len(rows),
            "sampled_separation_m": [row["pedestrian_to_ego_distance_m"] for row in rows],
            "legal_danger_judgment": None}


def measure_exceptions(files, measurement):
    return {"status": files["exception_review"]["status"],
            "source_refs": files["exception_review"]["source_refs"]}


def measure_governing(files, measurement):
    return {"original_device_condition": measurement["summary"]["measured_device_condition"],
            "other_governing_control_review_required":
                measurement["summary"]["measured_device_condition"] == "operating"}


def build_report(root):
    root = Path(root).resolve()
    config = read(required(root, "config.json"))
    scene = read(required(root, "scene.json"))
    if config.get("selected_case_id") != scene.get("case_id"):
        raise ValueError("Selected case and scene differ")
    capture, index, files = source(root)
    diagnostic_dimensions = config.get("diagnostic_camera_dimensions")
    if diagnostic_dimensions is not None and config.get("diagnostic_only") is not True:
        raise ValueError("Diagnostic camera dimensions require diagnostic-only configuration")
    diagnostic = index["format"] == "c111610-diagnostic-source-index-v1"
    if diagnostic:
        measurement = diagnostic_measurement(root, scene, index, files)
        receipt = {"joined_frames": measurement["frame_count"],
                   "physical_source_verified": False, "diagnostic_fixture": True}
        write(root / "saved-delivery-join.json", receipt)
    else:
        receipt = join(capture, root / "scene.json", root / "saved-delivery-join.json",
                       dimensions=diagnostic_dimensions)
        measurement = read(required(root, "saved-delivery-join-measurement.json"))
    observations = measurement["measurements"]
    if (len(observations) != receipt["joined_frames"] or
            (not diagnostic and len(observations) != 600)):
        raise ValueError("Original saved observation count differs")
    sealed_native = (not diagnostic and (root / "capture-seal.json").is_file() and
                     read(root / "capture-seal.json").get("provenance_kind") == "native" and
                     not read(root / "capture-seal.json").get("diagnostic_fixture") and
                     diagnostic_dimensions is None)
    source_hashes = {"capture/" + name + ".json": index["files"][name]["sha256"]
                     for name in ("site", "ego", "pedestrian", "exception_review")}
    methods = {
        "device_condition": (measure_device, ("capture/site.json",)),
        "directional_half_geometry": (measure_geometry, ("capture/site.json",)),
        "destination_occupancy_frames": (measure_destination,
                                         ("capture/site.json", "capture/ego.json", "capture/pedestrian.json")),
        "opposite_approach_context": (measure_opposite,
                                      ("capture/site.json", "capture/ego.json", "capture/pedestrian.json")),
        "exception_applicability_review": (measure_exceptions, ("capture/exception_review.json",)),
        "operating_device_context": (measure_governing, ("capture/site.json",)),
    }
    selected = {key: {"method": fn.__name__, "value": fn(files, measurement),
                      "sources": {name: source_hashes[name] for name in names}}
                for key, (fn, names) in methods.items()}
    return {"format": "worker-analysis-report", "case_id": scene["case_id"],
            "analysis_complete": True,
            "measurements": selected,
            "source_index_sha256": digest(capture / "source-index.json"),
            "saved_delivery_sha256": digest(root / "saved-delivery-join.json"),
            "provenance_kind": "original_saved_source" if sealed_native else "synthetic_fixture",
            "diagnostic_fixture": not sealed_native,
            "legal_verdict_claimed": False, "physical_acceptance_claimed": False,
            "limitations": ["Native origin and actual physical motion require independent corroboration.",
                            "Opposite-half danger, yielding and introductory exceptions remain unresolved."]}


def build_result(root, report):
    root = Path(root).resolve()
    config = read(required(root, "config.json"))
    capture, index, files = source(root)
    rows = files["frame_map"]
    ego = files["ego"]
    people = files["pedestrian"]
    media = files["camera_manifest"]
    observations = read(required(root, "saved-delivery-join-measurement.json"))["measurements"]
    count = 600 if index["format"] == "c111610-native-source-index-v1" else len(rows)
    if any(len(value) != count for value in (rows, ego, people, media, observations)):
        raise ValueError("Original source frame join differs")
    if index["format"] == "c111610-native-source-index-v1":
        encode_saved_views(root, capture)
    elif not all((root / (name + ".mkv")).is_file() for name in VIEWS):
        raise ValueError("Missing required source: four diagnostic camera videos")
    trace, mapping = [], []
    for i, (clock, driver, person, camera) in enumerate(zip(rows, ego, people, media)):
        if any(value["native_frame"] != clock["native_frame"] or
               value["native_elapsed_s"] != clock["native_elapsed_s"]
               for value in (driver, person, camera)):
            raise ValueError("Original actor/camera clock differs")
        point = driver["body_center_xy_m"]
        heading = driver.get("heading_deg", 0.0)
        speed = driver.get("speed_mps", 0.0)
        if not all(isinstance(v, (int, float)) and math.isfinite(v)
                   for v in (*point, heading, speed)):
            raise ValueError("Nonfinite original ego motion")
        trace.append({"frame": clock["native_frame"],
                      "time_s": clock["native_elapsed_s"],
                      "position": {"x": point[0], "y": point[1], "z": driver.get("z_m", 0)},
                      "position_m": [point[0], point[1], driver.get("z_m", 0)],
                      "heading_deg": heading, "speed_mps": speed,
                      "control": {"brake": driver.get("brake")}})
        mapping.append({"video_frame": i, "carla_frame": clock["native_frame"],
                        "native_frame": clock["native_frame"],
                        "time_s": clock["native_elapsed_s"]})
    for name, generated in (("trace.jsonl", trace), ("video_frames.jsonl", mapping)):
        path = root / name
        if path.exists():
            existing = [json.loads(line) for line in path.read_text().splitlines()]
            if len(existing) != count or any(
                (a.get("frame") if name == "trace.jsonl" else a.get("carla_frame")) !=
                (b.get("frame") if name == "trace.jsonl" else b.get("carla_frame")) or
                abs(a["time_s"] - b["time_s"]) > 1e-6 for a, b in zip(existing, generated)):
                raise ValueError("Original trace/frame map differs from selected analysis")
        else:
            path.write_text("".join(json.dumps(v) + "\n" for v in generated))
    description = config["case"]["recording_description"]
    channels = description["channels"]
    values = (
        lambda i: {"site_source_sha256": index["files"]["site"]["sha256"],
                   "map_name": index["map_name"]},
        lambda i: {"site_source_sha256": index["files"]["site"]["sha256"],
                   "in_crosswalk": observations[i]["pedestrian_in_crosswalk"]},
        lambda i: {"site_source_sha256": index["files"]["site"]["sha256"],
                   "on_destination_half": observations[i]["pedestrian_on_destination_half"]},
        lambda i: {"condition": observations[i]["device_condition"],
                   "site_source_sha256": index["files"]["site"]["sha256"]},
        lambda i: ego[i],
        lambda i: people[i],
        lambda i: files["exception_review"],
        lambda i: media[i],
    )
    if len(channels) != len(values):
        raise ValueError("Recording channel inventory differs")
    evidence = []
    for n, (channel, value) in enumerate(zip(channels, values)):
        name = f"recording-channel-{n}.jsonl"
        with (root / name).open("w") as stream:
            for i, clock in enumerate(rows):
                stream.write(json.dumps({"time_s": clock["native_elapsed_s"],
                                         "value": value(i)}) + "\n")
        evidence.append({"name": channel["name"], "unit": channel["unit"],
                         "reference": name})
    contexts = description["context_inputs"]
    for n, (name, value) in enumerate((("reviewed_original_site", files["site"]),
                                       ("reviewed_exception_context", files["exception_review"]))):
        reference = f"recording-context-{n}.json"
        write(root / reference, {name: value})
        evidence.append({"name": contexts[n]["name"], "unit": contexts[n]["unit"],
                         "reference": reference})
    check = {"target": "source_sealed_observation_count", "requested": count,
             "measured": len(observations), "method": "sealed frame and camera join",
             "tolerance": 0, "matched": len(observations) == count,
             "physical_cause_confirmed": False,
             "cause_evidence": "Original motion and pixel visibility still require review"}
    result = {"case_id": report["case_id"],
              "measured_values": {k: v["value"] for k, v in report["measurements"].items()},
              "target_checks": [check], "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "saved source processing; physical completion unverified",
              "physical_failure_flags": ["physical_completion_unverified"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description,
              "recording_evidence": evidence, "realized_observables": {},
              "provenance_kind": report["provenance_kind"],
              "diagnostic_fixture": report["diagnostic_fixture"],
              "legal_verdict_claimed": False,
              "physical_acceptance_claimed": False}
    target = root / "result.json"
    if target.exists():
        raise ValueError("Retain prior result; use a fresh analysis attempt")
    write(target, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.attempt)
    report = build_report(root)
    build_result(root, report)
    write(Path(args.output), report)


if __name__ == "__main__":
    main()
