"""Independent original-source audit for a Native NRS 484B.407 attempt.

The local operator copies this file beside its saved attempt. Diagnostic output
is deliberately ineligible for physical delivery acceptance.
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
    raise RuntimeError("Pinned runtime unavailable")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange import media

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing original source: " + str(path))
    return json.loads(path.read_text())


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing original source: " + str(path))
    result = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not result:
        raise ValueError("Empty original source: " + str(path))
    return result


def finite_vector(value, count):
    return (isinstance(value, list) and len(value) == count and
            all(type(x) in (int, float) and math.isfinite(x) for x in value))


def validate_originals(attempt, case_id, expected_frames):
    """Join original frame map, motion, trace, ray evidence and participants."""
    attempt = Path(attempt)
    names = ("video_frames.jsonl", "motion_history.jsonl", "trace.jsonl",
             "capture/evidence.jsonl", "turn_history.jsonl")
    streams = [rows(attempt / name) for name in names]
    if any(len(stream) != expected_frames for stream in streams):
        raise ValueError("Original source frame count differs from planned capture")
    config = read(attempt / "config.json")
    if config.get("selected_case_id") != case_id:
        raise ValueError("Exact delivery case differs")
    if expected_frames != config.get("rate_hz", 0) * config.get("duration_s", 0):
        raise ValueError("Original sources do not cover planned duration")
    site_ref = config.get("site_source", {})
    site_path = (attempt / site_ref.get("path", "missing-site")).resolve()
    if attempt.resolve() not in site_path.parents or not site_path.is_file() or sha(site_path) != site_ref.get("sha256"):
        raise ValueError("Exact original site source changed")
    site = read(site_path)
    lane_ids = {v["lane_id"] for v in site["incoming_lanes"].values()}
    if len(lane_ids) != 2:
        raise ValueError("Two approach lanes required")
    participants_seen = set()
    natives = []
    first_time = streams[0][0].get("time_s")
    for index, (frame, motion, trace, capture, turn) in enumerate(zip(*streams)):
        native, time_s = frame.get("native_frame"), frame.get("time_s")
        if (frame.get("video_frame") != index or motion.get("video_frame") != index or
                motion.get("native_frame") != native or trace.get("frame") != native or
                capture.get("original_frame") != native or turn.get("frame") != native or
                not type(time_s) in (int, float) or not math.isfinite(time_s) or
                not math.isclose(time_s - first_time, index / config["rate_hz"], abs_tol=.005) or
                any(abs(other.get(key, float("inf")) - time_s) > .001 for other, key in
                    ((trace, "time_s"), (capture, "recording_time_s"), (turn, "time_s")))):
            raise ValueError("Original frame/time join differs")
        natives.append(native)
        approaches = motion.get("approaches", {})
        if set(approaches) != {"approach_a", "approach_b"}:
            raise ValueError("Both original approaching vehicles required")
        for direction, actor in approaches.items():
            lane = site["incoming_lanes"][direction]
            if actor.get("road_lane") != [lane["road_id"], lane["lane_id"]]:
                raise ValueError("Original approaching lane differs")
        original = capture.get("original_observations", {})
        if original.get("frame") != native or abs(original.get("time_s", float("inf")) - time_s) > .001:
            raise ValueError("Participant observation frame/time differs")
        people = original.get("participants")
        if not isinstance(people, list) or len(people) < 3:
            raise ValueError("Missing complete participant inventory")
        ids = [p.get("actor_id") for p in people if isinstance(p, dict)]
        if len(ids) != len(people) or len(set(ids)) != len(ids) or capture.get("actor_id") not in ids:
            raise ValueError("Missing complete participant inventory")
        for person in people:
            vertices = person.get("body_vertices_m")
            if (not finite_vector(person.get("position_m"), 3) or
                    not finite_vector(person.get("velocity_mps"), 3) or
                    not isinstance(vertices, list) or len(vertices) < 8 or
                    not all(finite_vector(vertex, 3) for vertex in vertices)):
                raise ValueError("Missing complete participant bodies")
        participants_seen.update(ids)
        visibility = capture.get("visibility", {})
        if set(visibility.get("required_lane_ids", [])) != lane_ids or {
                row.get("lane_id") for row in visibility.get("approaches", [])} != lane_ids:
            raise ValueError("Original two-direction ray evidence missing")
    if natives != sorted(set(natives)):
        raise ValueError("Original Native frames unordered or repeated")
    return {"frames": expected_frames, "participant_ids": sorted(participants_seen),
            "source_sha256": {name: sha(attempt / name) for name in names},
            "site_sha256": sha(site_path)}


def review_checker(samples, width, height):
    pending = {}
    for row in samples:
        pending.setdefault(row["video_frame"], []).append(row)
    seen = set()

    def inspect(frame):
        if (frame.width, frame.height) != (width, height):
            raise ValueError("Reviewed camera dimensions differ")
        for row in pending.get(frame.index, []):
            box = row.get("bbox_xyxy")
            if not isinstance(box, list) or len(box) != 4 or not all(type(n) is int for n in box):
                raise ValueError("Missing reviewed actor pixel box")
            x0, y0, x1, y1 = box
            if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height and (x1-x0)*(y1-y0) >= 16):
                raise ValueError("Reviewed actor pixel box outside source")
            pixels = {frame.pixels[3*(y*width+x):3*(y*width+x)+3]
                      for y in range(y0, y1) for x in range(x0, x1)}
            if len(pixels) < 2:
                raise ValueError("Reviewed actor ROI has no pixel detail")
            seen.add(frame.index)

    def finish():
        if seen != set(pending):
            raise ValueError("Reviewed actor frame was not decoded")
    return inspect, finish


def audit(attempt, case_id, job_id, attempt_number, recording_id, review_path, output, decode_receipt):
    attempt, output, decode_receipt = (Path(p).resolve() for p in (attempt, output, decode_receipt))
    if attempt not in output.parents or attempt in decode_receipt.parents or output.name == "result.json":
        raise ValueError("Audit output must be under attempt and decode receipt outside it")
    result = read(attempt / "result.json")
    if (result.get("case_id") != case_id or result.get("provenance_kind") != "native" or
            result.get("diagnostic_fixture") is not False or result.get("physical_acceptance_claimed") is not False):
        raise ValueError("Native non-diagnostic result required")
    seal = read(attempt / "capture-seal.json")
    if (seal.get("format") != "worker-sealed-capture" or seal.get("provenance_kind") != "native" or
            seal.get("diagnostic_fixture") is not False):
        raise ValueError("Native capture seal required")
    required = {"config.json", "trace.jsonl", "motion_history.jsonl", "video_frames.jsonl",
                "capture/evidence.jsonl", "turn_history.jsonl", *(name + ".mkv" for name in CAMERAS)}
    if not required <= set(seal.get("sources", {})):
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
    joined = validate_originals(attempt, case_id, seal["frames"])
    if any(result.get("source_evidence_hashes", {}).get(name) != digest
           for name, digest in joined["source_sha256"].items()):
        raise ValueError("Saved result original source binding changed")
    physical = result.get("physical_checks", {})
    if any(physical.get(key, {}).get("status") != "met" for key in ("setup", "target", "maneuver", "attempt")):
        raise ValueError("Physical completion absent from Native source assessment")
    if not result.get("realized_observables"):
        raise ValueError("Physical completion lacks realized source observations")
    cameras = {name: attempt / (name + ".mkv") for name in CAMERAS}
    media.check_four_view_sources(cameras)
    review = read(review_path)
    if (not review.get("reviewer") or not review.get("method") or review.get("case_id") != case_id or
            review.get("frame_map_sha256") != joined["source_sha256"]["video_frames.jsonl"] or
            review.get("source_sha256") != {name: sha(path) for name, path in cameras.items()}):
        raise ValueError("Independent pixel review missing or changed")
    observations = review.get("observations", [])
    if not observations or not set(joined["participant_ids"]) <= {x.get("actor_id") for x in observations}:
        raise ValueError("Independent pixel review omits a participant")
    from worker_exchange.capture import PROFILE
    dimensions = {"overview": PROFILE["overview"], **dict(zip(CAMERAS[1:], PROFILE["detail_views"]))}
    for name, path in cameras.items():
        samples = [x for x in observations if x.get("camera") == name]
        if not samples:
            raise ValueError("Independent pixel review omits camera: " + name)
        inspect, finish = review_checker(samples, *dimensions[name])
        media.audit(path, joined["frames"], checkers={"reviewed_actor_pixels": (sha(__file__), inspect)},
                    mapping_sha256=joined["source_sha256"]["video_frames.jsonl"])
        finish()
    video, trace = attempt / "raw.mkv", attempt / "converted/trace.json"
    decoded = media.audit(video, joined["frames"],
                          mapping_sha256=joined["source_sha256"]["video_frames.jsonl"], receipt=decode_receipt)
    scenes = read(trace)["scenes"]
    if len(scenes) != joined["frames"] or any(scene["t"] != round(row["time_s"] * 1000)
            for scene, row in zip(scenes, rows(attempt / "video_frames.jsonl"))):
        raise ValueError("Converted trace/original time join differs")
    report = {"format": "worker-delivery-audit", "passed": True, "physical_acceptance_claimed": False,
              "case_id": case_id, "job_id": job_id, "attempt": attempt_number, "recording_id": recording_id,
              "checks": {key: True for key in CHECKS}, "frames": joined["frames"],
              "source_result_sha256": sha(attempt / "result.json"), "video": "raw.mkv", "video_sha256": sha(video),
              "trace": "converted/trace.json", "trace_sha256": sha(trace), "original_sources": joined,
              "pixel_review_sha256": sha(review_path), "auditor_path": str(Path(__file__).resolve()),
              "auditor_sha256": sha(__file__), "source_decode_receipt_path": str(decode_receipt),
              "source_decode_receipt_sha256": sha(decode_receipt),
              "source_decode_auditor_sha256": decoded["auditor_sha256"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in ("case", "job-id", "recording-id"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--attempt-number", type=int, required=True)
    for key in ("attempt", "pixel-review", "output", "decode-receipt"):
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.job_id, args.attempt_number, args.recording_id,
                           args.pixel_review, args.output, args.decode_receipt), sort_keys=True))
