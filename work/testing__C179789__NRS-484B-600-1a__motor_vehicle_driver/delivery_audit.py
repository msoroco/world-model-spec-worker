"""Independent saved-source and full-decode audit for one exact speed case.

Passing this CPU audit does not establish a reasonable/proper speed, visible
participants, or canonical physical acceptance. Original image review remains.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from native_camera import VIEWS


SOURCES = ("authored-setup.json", "authored-setup-seal.json",
           "original-conditions.jsonl", "original-conditions-seal.json",
           "trace.jsonl", "video_frames.jsonl", "media-receipt.json",
           "native-run-status.json")
FIELDS = ("ego_speed_mps", "leader_gap_m", "highway_width_m", "surface_wetness",
          "precipitation_strength", "fog_density", "tire_friction")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def document(path: Path) -> dict:
    if not path.is_file():
        raise ValueError("missing audit source: " + path.name)
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError("missing audit source: " + path.name)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _point(value, label: str) -> tuple[float, float, float]:
    if (not isinstance(value, list) or len(value) != 3 or
            any(type(x) not in (int, float) or not math.isfinite(x) for x in value)):
        raise ValueError("missing original participant position: " + label)
    return tuple(float(x) for x in value)


def _video(path: Path, width: int, height: int, trace: list[dict], name: str) -> dict:
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                            "-select_streams", "v:0", "-show_entries",
                            "stream=codec_name,width,height,r_frame_rate,nb_read_frames",
                            "-of", "json", str(path)], capture_output=True, text=True,
                           check=True)
    streams = json.loads(probe.stdout).get("streams", [])
    if (len(streams) != 1 or streams[0].get("codec_name") != "ffv1" or
            streams[0].get("width") != width or streams[0].get("height") != height or
            streams[0].get("r_frame_rate") != "20/1" or
            streams[0].get("nb_read_frames") != "900"):
        raise ValueError("full video decode, dimensions or frame count differ: " + name)
    samples = (0, 450, 899)
    selector = "+".join(f"eq(n\\,{index})" for index in samples)
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path),
                              "-vf", "select=" + selector, "-fps_mode", "passthrough",
                              "-f", "rawvideo", "-pix_fmt", "bgra", "pipe:1"],
                             capture_output=True, check=True).stdout
    stride = width * height * 4
    if len(decoded) != len(samples) * stride:
        raise ValueError("full video sample decode differs: " + name)
    sample_hashes = {}
    for offset, index in enumerate(samples):
        pixels = decoded[offset * stride:(offset + 1) * stride]
        expected = trace[index]["camera_sources"][name]
        digest = hashlib.sha256(pixels).hexdigest()
        if digest != expected.get("sha256"):
            raise ValueError("decoded original pixel hash differs: " + name)
        rgb = [pixels[i:i + 3] for i in range(0, len(pixels), 4)]
        if not any(any(pixel) for pixel in rgb) or len(set(rgb)) < 2:
            raise ValueError("decoded original pixels lack scene texture: " + name)
        sample_hashes[str(index)] = digest
    return {"sha256": sha(path), "frames_fully_decoded": 900, "fps": 20,
            "width": width, "height": height, "sample_sha256": sample_hashes,
            "actual_pixels_decoded": True,
            "participant_visibility_verified": False}


def audit(attempt: Path, *, diagnostic_test: bool = False,
          diagnostic_views=None) -> dict:
    """Independently rejoin retained sources and fully decode each view."""
    attempt = Path(attempt).resolve()
    if diagnostic_views is not None and not diagnostic_test:
        raise ValueError("diagnostic camera override requires diagnostic test mode")
    views = diagnostic_views if diagnostic_views is not None else VIEWS
    report_path = attempt / "analysis-report.json"
    result_path = attempt / "result.json"
    report, result = document(report_path), document(result_path)
    setup = document(attempt / "authored-setup.json")
    setup_seal = document(attempt / "authored-setup-seal.json")
    condition_seal = document(attempt / "original-conditions-seal.json")
    status = document(attempt / "native-run-status.json")
    media = document(attempt / "media-receipt.json")
    case = setup.get("case_id")
    plan = document(Path(__file__).resolve().parent / "case-plan.json")
    if (case not in {item["case_id"] for item in plan["cases"]} or
            report.get("case_id") != case or result.get("case_id") != case or
            setup_seal.get("case_id") != case or condition_seal.get("case_id") != case or
            status.get("case_id") != case):
        raise ValueError("audit exact case binding differs")
    if (setup_seal.get("sha256") != sha(attempt / "authored-setup.json") or
            condition_seal.get("sha256") != sha(attempt / "original-conditions.jsonl") or
            setup.get("source_packet_sha256") != media.get("source_packet_sha256") or
            status.get("errors") != [] or
            status.get("restoration", {}).get("restored") is not True or
            status.get("capture", {}).get("frames") != 900):
        raise ValueError("original capture seal, source or restoration differs")
    diagnostic = condition_seal.get("diagnostic_fixture")
    if diagnostic is not diagnostic_test or report.get("physical_acceptance_claimed") is not False or (
            result.get("physical_acceptance_claimed") is not False):
        raise ValueError("audit provenance or physical claim differs")
    expected_names = (*SOURCES, *(name + ".mkv" for name, _, _ in views))
    hashes = report.get("sources")
    if not isinstance(hashes, dict):
        raise ValueError("saved analysis source hashes missing")
    for name in expected_names:
        path = attempt / name
        if not path.is_file() or hashes.get(name) != sha(path):
            raise ValueError("missing or stale saved analysis source: " + name)
    if (media.get("trace_sha256") != hashes["trace.jsonl"] or
            media.get("frame_map_sha256") != hashes["video_frames.jsonl"] or
            media.get("frames") != 900 or
            media.get("video_sha256") !=
            {name: hashes[name + ".mkv"] for name, _, _ in views}):
        raise ValueError("original media receipt differs from saved analysis")
    trace = rows(attempt / "trace.jsonl")
    mapping = rows(attempt / "video_frames.jsonl")
    conditions = rows(attempt / "original-conditions.jsonl")
    if len(trace) != 900 or len(mapping) != 900 or len(conditions) != 900:
        raise ValueError("original 900-frame source set incomplete")
    actor_ids = conditions[0].get("source_ids", {})
    if not actor_ids.get("ego_actor_id") or not actor_ids.get("leader_actor_id"):
        raise ValueError("original participant actor identities missing")
    for index, (row, frame_map, condition) in enumerate(zip(trace, mapping, conditions)):
        frame, time_s = condition.get("frame"), condition.get("time_s")
        if (type(frame) is not int or type(time_s) not in (int, float) or
                row.get("frame") != frame or row.get("time_s") != time_s or
                frame_map.get("video_frame") != index or
                frame_map.get("native_frame") != frame or
                frame_map.get("carla_frame") != frame or
                frame_map.get("time_s") != time_s or
                condition.get("source_ids") != actor_ids or
                row.get("source_packet_sha256") != setup["source_packet_sha256"] or
                row.get("condition_sample_index") != index or
                (index and (frame != trace[index - 1]["frame"] + 1 or
                            not .049 <= time_s - trace[index - 1]["time_s"] <= .051))):
            raise ValueError("original participant/frame/time join differs")
        ego, leader = _point(row.get("position_m"), "ego"), _point(
            row.get("leader_position_m"), "leader")
        if math.dist(ego, leader) <= 0:
            raise ValueError("original participants overlap")
        cameras, camera_hashes = row.get("camera_sources"), frame_map.get("camera_source_sha256")
        if (not isinstance(cameras, dict) or not isinstance(camera_hashes, dict) or
                set(cameras) != {name for name, _, _ in views} or
                set(camera_hashes) != set(cameras)):
            raise ValueError("original four-camera join missing")
        for name, width, height in views:
            item = cameras[name]
            if (not isinstance(item, dict) or item.get("frame") != frame or
                    item.get("width") != width or item.get("height") != height or
                    camera_hashes[name] != item.get("sha256") or
                    type(item.get("time_s")) not in (int, float) or
                    abs(item["time_s"] - time_s) > .05):
                raise ValueError("original camera identity differs")
    measured = result.get("measured_values", {})
    retained = measured.get("conditions", {})
    if (retained.get("sample_count") != 900 or
            retained.get("diagnostic_fixture") is not diagnostic_test or
            retained.get("full_history") != conditions or
            retained.get("source", {}).get("sha256") != hashes["original-conditions.jsonl"] or
            result.get("measured_values", {}).get("legal_judgment") != "unresolved" or
            result.get("trace_reference") != "trace.jsonl" or
            result.get("video_frame_map_reference") != "video_frames.jsonl" or
            result.get("video_references") != [name + ".mkv" for name, _, _ in views]):
        raise ValueError("saved Native result differs from original sources")
    steady = {name: sum(row[name] for row in conditions[180:]) / 720 for name in FIELDS}
    travel = math.dist(_point(trace[0]["position_m"], "first ego"),
                       _point(trace[-1]["position_m"], "last ego"))
    observation = report.get("measurements", {}).get("basic_speed_observation", {})
    value = observation.get("value", {})
    if (measured.get("steady_means") != steady or
            measured.get("travel_progress_m") != travel or
            value.get("steady_means") != steady or
            value.get("travel_progress_m") != travel or
            value.get("source_ids") != actor_ids or
            value.get("legal_judgment") != "unresolved" or
            observation.get("sources") != {name: hashes[name] for name in
                                           ("authored-setup.json", "original-conditions.jsonl",
                                            "trace.jsonl")} or
            result.get("maneuver_completed") is not (travel >= .25)):
        raise ValueError("saved measurement differs from original values")
    requests = setup.get("variables", {})
    target_plan = (("ego_speed_mps", "ego_speed_request_mps", 1.0),
                   ("leader_gap_m", "leader_initial_gap_m", 3.0),
                   ("surface_wetness", "surface_wetness_request", .05),
                   ("highway_width_m", "highway_width_m", .05),
                   ("precipitation_strength", "native_precipitation_request", 2.0),
                   ("fog_density", "native_fog_request", 2.0))
    checks = result.get("target_checks")
    if not isinstance(checks, list) or len(checks) != len(target_plan):
        raise ValueError("saved target checks missing")
    for check, (name, request_key, tolerance) in zip(checks, target_plan):
        request = requests.get(request_key)
        if (type(request) not in (int, float) or
                check.get("target") != name or check.get("requested") != request or
                check.get("measured") != steady[name] or
                check.get("tolerance") != tolerance or
                check.get("matched") is not (abs(steady[name] - request) <= tolerance) or
                check.get("physical_cause_confirmed") is not False):
            raise ValueError("saved target check differs from original values")
    decodes = {name: _video(attempt / (name + ".mkv"), width, height, trace, name)
               for name, width, height in views}
    return {"format": "worker-delivery-audit", "case_id": case,
            "status": "cpu_source_audit_passed", "frame_count": 900,
            "native_result_sha256": sha(result_path),
            "analysis_report_sha256": sha(report_path),
            "original_source_hashes": hashes,
            "full_video_decode": decodes,
            "checks": {"native_source": True, "all_participants": True,
                       "time_join": True, "full_video_decode": True,
                       "actual_pixels": True,
                       "physical_completion": bool(result.get("maneuver_completed"))},
            "diagnostic_audit_test_passed": diagnostic_test,
            "participant_visibility_verified": False,
            "legal_judgment": "unresolved",
            "physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt), indent=2))
