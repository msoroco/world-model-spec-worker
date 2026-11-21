"""Independent, source-bound audit for an exact C24757 delivery attempt.

Diagnostic sources can exercise the software checks but cannot pass delivery.
The local dispatcher must place this file and its decode receipt in the batch's
state/operations/worker_exchange directory before acceptance.
"""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

REPO = next((p for p in Path(__file__).resolve().parents
             if (p / "runtime/scenario_pipeline").is_dir()), None)
if REPO is None:
    raise RuntimeError("Pinned scenario runtime missing")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange import media

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing original source: " + path.name)
    data = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not data:
        raise ValueError("Empty original source: " + path.name)
    return data


def validate_join(attempt, case_id, frame_count):
    """Verify every original frame and both complete vehicle bodies."""
    attempt = Path(attempt)
    mapping = rows(attempt / "video_frames.jsonl")
    history = rows(attempt / "vehicle_signal_history.jsonl")
    trace = rows(attempt / "trace.jsonl")
    if not len(mapping) == len(history) == len(trace) == frame_count:
        raise ValueError("Original source frame count differs from capture seal")
    previous = (-1, -1.0)
    for index, (frame, motion, captured) in enumerate(zip(mapping, history, trace)):
        native = frame.get("carla_frame")
        time_s = frame.get("time_s")
        if (frame.get("video_frame") != index or type(native) is not int
                or type(time_s) not in (int, float) or not math.isfinite(time_s)
                or native <= previous[0] or time_s <= previous[1]
                or any(item.get("frame") != native or item.get("time_s") != time_s
                       for item in (motion, captured))):
            raise ValueError("Original frame/time join differs")
        if captured.get("case_id", case_id) != case_id:
            raise ValueError("Trace case differs from exact delivery case")
        for role in ("ego", "other"):
            actor = motion.get(role)
            body = actor.get("body_vertices_xy_m") if isinstance(actor, dict) else None
            if (not isinstance(body, list) or len(body) < 4
                    or any(not isinstance(vertex, list) or len(vertex) != 2
                           or any(type(value) not in (int, float) or not math.isfinite(value)
                                  for value in vertex) for vertex in body)
                    or type(actor.get("speed_mps")) not in (int, float)
                    or not math.isfinite(actor["speed_mps"])):
                raise ValueError("Missing complete participant body: " + role)
        if (motion.get("signal_state") != "Off" or motion.get("other_signal_state") != "Off"
                or motion.get("native_signal_id") == motion.get("other_native_signal_id")
                or not all(type(motion.get(key)) is int for key in
                           ("native_signal_id", "other_native_signal_id"))):
            raise ValueError("Two distinct governing Off signal sources required")
        previous = (native, time_s)
    return {"frames": frame_count, "frame_map_sha256": sha(attempt / "video_frames.jsonl"),
            "history_sha256": sha(attempt / "vehicle_signal_history.jsonl"),
            "native_trace_sha256": sha(attempt / "trace.jsonl")}


def pixel_checker(samples, width, height):
    pending = {}
    for row in samples:
        pending.setdefault(row["video_frame"], []).append(row)
    seen = set()
    def inspect(frame):
        if (frame.width, frame.height) != (width, height):
            raise ValueError("Reviewed camera dimensions differ")
        for row in pending.get(frame.index, []):
            box = row.get("bbox_xyxy")
            if (not isinstance(box, list) or len(box) != 4 or any(type(x) is not int for x in box)):
                raise ValueError("Missing reviewed actor pixel box")
            x0, y0, x1, y1 = box
            if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
                raise ValueError("Reviewed actor pixel box outside source")
            pixels = set()
            for y in range(y0, y1):
                for x in range(x0, x1):
                    offset = 3 * (y * width + x)
                    pixels.add(frame.pixels[offset:offset + 3])
                    if len(pixels) > 1:
                        break
                if len(pixels) > 1:
                    break
            if len(pixels) < 2:
                raise ValueError("Reviewed actor ROI has no visible pixel detail")
        seen.add(frame.index)
    def finish():
        if not set(pending) <= seen:
            raise ValueError("Reviewed actor pixel frame was not decoded")
    return inspect, finish


def audit_attempt(attempt, case_id, job_id, attempt_number, recording_id, review_path,
                  output, decode_receipt, *, diagnostic_selftest=False):
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    decode_receipt = Path(decode_receipt).resolve()
    if output.name == "result.json" or attempt not in output.parents or attempt in decode_receipt.parents:
        raise ValueError("Audit and decode receipt locations differ from contract")
    result = read(attempt / "result.json")
    expected = "synthetic_fixture" if diagnostic_selftest else "native"
    if (result.get("case_id") != case_id or result.get("provenance_kind") != expected
            or result.get("diagnostic_fixture") is not diagnostic_selftest
            or result.get("physical_acceptance_claimed") is not False):
        raise ValueError("Native exact-case result required")
    seal = read(attempt / "capture-seal.json")
    required = {"config.json", "trace.jsonl", "vehicle_signal_history.jsonl",
                "video_frames.jsonl", "junction_context.json", *(name + ".mkv" for name in CAMERAS)}
    if (seal.get("format") != "worker-sealed-capture" or seal.get("provenance_kind") != expected
            or seal.get("diagnostic_fixture") is not diagnostic_selftest
            or not required <= set(seal.get("sources", {}))):
        raise ValueError("Capture seal omits required original source")
    for name, digest in seal["sources"].items():
        source = (attempt / name).resolve()
        if attempt not in source.parents or not source.is_file() or sha(source) != digest:
            raise ValueError("Sealed original source changed: " + name)
    if read(attempt / "native-exit.json").get("capture_seal_sha256") != sha(attempt / "capture-seal.json"):
        raise ValueError("Native exit does not bind capture seal")
    owner = read(attempt / "owner-release.json")
    if owner.get("operator_attested") is not True or owner.get("native_exit_sha256") != sha(attempt / "native-exit.json"):
        raise ValueError("Owner release does not bind Native exit")
    joined = validate_join(attempt, case_id, seal["frames"])
    config = read(attempt / "config.json")
    if joined["frames"] != config["rate_hz"] * config["duration_s"]:
        raise ValueError("Original sources do not cover full planned duration")
    physical = result.get("physical_checks", {})
    if (physical.get("setup", {}).get("status") != "met"
            or physical.get("maneuver", {}).get("status") != "met"
            or not result.get("realized_observables")):
        raise ValueError("Physical completion absent from Native source assessment")
    sources = {name: attempt / (name + ".mkv") for name in CAMERAS}
    media.check_four_view_sources(sources)
    review = read(review_path)
    if (review.get("case_id") != case_id or not review.get("reviewer") or not review.get("method")
            or review.get("frame_map_sha256") != joined["frame_map_sha256"]
            or review.get("source_sha256") != {name: sha(path) for name, path in sources.items()}):
        raise ValueError("Independent pixel review source binding changed")
    observations = review.get("observations", [])
    if not {"ego", "other"} <= {row.get("actor") for row in observations}:
        raise ValueError("Independent pixel review omits participant")
    from worker_exchange.capture import PROFILE
    dimensions = {"overview": PROFILE["overview"],
                  **dict(zip(CAMERAS[1:], PROFILE["detail_views"]))}
    for name, source in sources.items():
        samples = [row for row in observations if row.get("camera") == name]
        if not samples or any(row.get("actor") not in ("ego", "other") or
                              type(row.get("video_frame")) is not int or
                              not 0 <= row["video_frame"] < joined["frames"] for row in samples):
            raise ValueError("Independent pixel review omits camera or frame: " + name)
        inspect, finish = pixel_checker(samples, *dimensions[name])
        media.audit(source, joined["frames"],
                    checkers={"reviewed_actor_pixels": (sha(Path(__file__)), inspect)},
                    mapping_sha256=joined["frame_map_sha256"])
        finish()
    video = attempt / "raw.mkv"
    decoded = media.audit(video, joined["frames"],
                          mapping_sha256=joined["frame_map_sha256"], receipt=decode_receipt)
    trace = attempt / "converted/trace.json"
    scenes = read(trace)["scenes"]
    if len(scenes) != joined["frames"] or any(scene["t"] != round(frame["time_s"] * 1000)
            for scene, frame in zip(scenes, rows(attempt / "video_frames.jsonl"))):
        raise ValueError("Core trace/original frame time join differs")
    audit = {"format": "worker-delivery-audit-diagnostic" if diagnostic_selftest else "worker-delivery-audit",
             "passed": not diagnostic_selftest, "software_checks_passed": True,
             "diagnostic_fixture": diagnostic_selftest, "physical_acceptance_claimed": False,
             "case_id": case_id, "job_id": job_id, "attempt": attempt_number,
             "recording_id": recording_id, "checks": {key: True for key in CHECKS},
             "frames": joined["frames"], "source_result_sha256": sha(attempt / "result.json"),
             "video": "raw.mkv", "video_sha256": sha(video), "trace": "converted/trace.json",
             "trace_sha256": sha(trace), "auditor_path": str(Path(__file__).resolve()),
             "auditor_sha256": sha(Path(__file__)), "source_decode_receipt_path": str(decode_receipt),
             "source_decode_receipt_sha256": sha(decode_receipt),
             "source_decode_auditor_sha256": decoded["auditor_sha256"],
             "original_sources": joined, "pixel_review_sha256": sha(review_path)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, indent=2) + "\n")
    return audit


def main():
    parser = argparse.ArgumentParser()
    for key in ("case", "job-id", "recording-id"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--attempt-number", type=int, required=True)
    for key in ("attempt", "pixel-review", "output", "decode-receipt"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--diagnostic-selftest", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit_attempt(args.attempt, args.case, args.job_id, args.attempt_number,
                                   args.recording_id, args.pixel_review, args.output,
                                   args.decode_receipt, diagnostic_selftest=args.diagnostic_selftest),
                     sort_keys=True))


if __name__ == "__main__":
    main()
