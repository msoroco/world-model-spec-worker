"""Independent prospective Native delivery audit for exact C144550 cases.

CPU fixtures exercise this boundary. Only a sealed Native capture with an
independent original-pixel review can produce an accepted delivery receipt.
"""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from worker_exchange import media  # noqa: E402


CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing original source: " + path.name)
    return json.loads(path.read_text())


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing original source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def selected(case_id):
    entries = read(HERE / "execution-manifest.json")["cases"]
    found = [entry for entry in entries if entry["case_id"] == case_id]
    if len(found) != 1:
        raise ValueError("Unknown exact C144550 case")
    return found[0]


def audit_sources(attempt, case_id):
    attempt = Path(attempt).resolve()
    result = read(attempt / "result.json")
    if result.get("case_id") != case_id:
        raise ValueError("Original result case differs")
    mapping = rows(attempt / "video_frames.jsonl")
    history = rows(attempt / "lane_history.jsonl")
    trace = rows(attempt / "trace.jsonl")
    capture = rows(attempt / "capture/evidence.jsonl")
    if not mapping or not len(mapping) == len(history) == len(trace) == len(capture):
        raise ValueError("Original participant/time source lengths differ")
    for index, (frame, body, control, evidence) in enumerate(zip(mapping, history, trace, capture)):
        original = frame.get("carla_frame")
        if frame.get("video_frame") != index or any(item.get("frame") != original for item in (body, control)) or evidence.get("original_frame") != original:
            raise ValueError("Original participant/frame join differs")
        time_s = frame.get("time_s")
        if not isinstance(time_s, (int, float)) or not math.isfinite(time_s) or any(
                not isinstance(item.get("time_s"), (int, float)) or abs(item["time_s"] - time_s) > .001
                for item in (body, control)) or not isinstance(evidence.get("recording_time_s"), (int, float)) or abs(evidence["recording_time_s"] - time_s) > .001:
            raise ValueError("Original participant/time join differs")
        if (not isinstance(body.get("ego_body_vertices_xy_m"), list) or len(body["ego_body_vertices_xy_m"]) < 4
                or not isinstance(body.get("target_lane_bodies"), list) or not body["target_lane_bodies"]):
            raise ValueError("Original ego or target body source missing")
        if any(not isinstance(target.get("body_vertices_xy_m"), list) or len(target["body_vertices_xy_m"]) < 4
               for target in body["target_lane_bodies"]):
            raise ValueError("Original target body geometry missing")
        participants = evidence.get("original_observations", {}).get("participants")
        if not isinstance(participants, list) or len(participants) < 2:
            raise ValueError("Original participant inventory missing")
        identities = [person.get("actor_id") for person in participants if isinstance(person, dict)]
        if (len(identities) != len(participants) or len(set(identities)) != len(identities)
                or evidence.get("actor_id") not in identities or any(
                    not isinstance(person.get("body_vertices_m"), list) or len(person["body_vertices_m"]) < 8
                    for person in participants)):
            raise ValueError("Original participant identity or body missing")
    return {"original_frame_count": len(mapping), "time_join": True,
            "all_participants": True, "lane_history_sha256": sha(attempt / "lane_history.jsonl")}


def verify_physical(result, attempt):
    attempt = Path(attempt).resolve()
    if result.get("physical_acceptance_claimed") is not False:
        raise ValueError("Result asserts physical acceptance before independent audit")
    for key in ("setup", "target", "maneuver"):
        check = result.get("physical_checks", {}).get(key, {})
        if check.get("status") != "met" or not check.get("method"):
            raise ValueError("Source-bound physical completion absent: " + key)
        sources = check.get("sources")
        if not isinstance(sources, dict) or not sources:
            raise ValueError("Physical completion source hashes absent: " + key)
        for name, digest in sources.items():
            source = (attempt / name).resolve()
            if attempt not in source.parents or not source.is_file() or sha(source) != digest:
                raise ValueError("Physical completion source changed: " + name)
    if not all(result.get(key) is True for key in ("setup_confirmed", "behavior_attempted", "maneuver_completed")):
        raise ValueError("Physical setup, selected target or maneuver not completed")


def verify_seal(attempt, diagnostic=False):
    attempt = Path(attempt).resolve()
    seal = read(attempt / "capture-seal.json")
    if (seal.get("format") != "worker-sealed-capture" or seal.get("provenance_kind") != "native"
            or seal.get("diagnostic_fixture") is not diagnostic
            or seal.get("restoration", {}).get("restored") is not True
            or not seal.get("encoder_exit_codes")
            or any(code != 0 for code in seal["encoder_exit_codes"].values())
            or seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"]):
        raise ValueError("Native capture seal provenance or closure differs")
    required = {"construction.json", "runner.py", "config.json", "lane_context.json", "lane_history.jsonl", "video_frames.jsonl",
                "trace.jsonl", "capture/evidence.jsonl", *(name + ".mkv" for name in CAMERAS)}
    sources = seal.get("sources")
    if not isinstance(sources, dict) or not required <= set(sources):
        raise ValueError("Native seal omits required original source")
    source_digest = hashlib.sha256(json.dumps(sources, sort_keys=True, separators=(",", ":"),
                                              ensure_ascii=False).encode()).hexdigest()
    if seal.get("source_digest") != source_digest:
        raise ValueError("Native seal source inventory digest differs")
    for name, digest in sources.items():
        source = (attempt / name).resolve()
        if attempt not in source.parents or not source.is_file() or sha(source) != digest:
            raise ValueError("Sealed original source changed: " + name)
    exit_receipt = read(attempt / "native-exit.json")
    if (exit_receipt.get("event") != "native_exit" or exit_receipt.get("capture_seal_sha256") != sha(attempt / "capture-seal.json")
            or exit_receipt.get("native_revision") != seal.get("native_revision")):
        raise ValueError("Native exit does not bind capture seal")
    if seal.get("native_revision") != {"construction_sha256": sha(attempt / "construction.json"),
                                        "runner_sha256": sha(attempt / "runner.py")}:
        raise ValueError("Native revision differs from original construction")
    owner = read(attempt / "owner-release.json")
    if (owner.get("event") != "owner_released" or owner.get("operator_attested") is not True
            or owner.get("native_exit_sha256") != sha(attempt / "native-exit.json")
            or owner.get("native_construction_sha256") != seal["native_revision"]["construction_sha256"]
            or owner.get("no_resource_operation_performed") is not True):
        raise ValueError("Owner release does not bind Native exit")
    return seal


def verify_review(attempt, case_id, review_path, frames):
    attempt = Path(attempt).resolve()
    review = read(review_path)
    config = read(attempt / "config.json")
    dimensions = {camera["name"]: (camera["width"], camera["height"]) for camera in config["cameras"]}
    sources = {name: sha(attempt / (name + ".mkv")) for name in CAMERAS}
    if (review.get("case_id") != case_id or not review.get("reviewer") or not review.get("method")
            or review.get("frame_map_sha256") != sha(attempt / "video_frames.jsonl")
            or review.get("lane_history_sha256") != sha(attempt / "lane_history.jsonl")
            or review.get("source_sha256") != sources):
        raise ValueError("Independent pixel review missing or stale")
    observations = review.get("observations", [])
    if not observations or {item.get("actor") for item in observations} != {"ego", "target"} or {item.get("camera") for item in observations} != set(CAMERAS):
        raise ValueError("Independent pixel review omits actor or camera")
    for name in CAMERAS:
        needed = [item for item in observations if item["camera"] == name]
        seen = set()
        width, height = dimensions[name]

        def check(frame):
            if (frame.width, frame.height) != (width, height):
                raise ValueError("Reviewed camera dimensions differ")
            for item in needed:
                if item["video_frame"] != frame.index:
                    continue
                box = item.get("bbox_xyxy")
                if (not isinstance(box, list) or len(box) != 4 or any(type(value) is not int for value in box)):
                    raise ValueError("Reviewed pixel box missing")
                x0, y0, x1, y1 = box
                if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height and (x1 - x0) * (y1 - y0) >= 16):
                    raise ValueError("Reviewed pixel box invalid")
                colors = set()
                for y in range(y0, y1):
                    for x in range(x0, x1):
                        offset = 3 * (y * width + x)
                        colors.add(frame.pixels[offset:offset + 3])
                        if len(colors) >= 2:
                            break
                    if len(colors) >= 2:
                        break
                if len(colors) < 2:
                    raise ValueError("Reviewed actor ROI has no visible pixel detail")
                seen.add((frame.index, item["actor"]))

        media.audit(attempt / (name + ".mkv"), frames,
                    checkers={"reviewed_actor_pixels": (sha(__file__), check)},
                    mapping_sha256=sha(attempt / "video_frames.jsonl"))
        if seen != {(item["video_frame"], item["actor"]) for item in needed}:
            raise ValueError("Reviewed actor pixel frame was not decoded")
    return sha(review_path)


def audit(attempt, case_id, pixel_review, output, diagnostic=False):
    attempt = Path(attempt).resolve()
    selected(case_id)
    seal = verify_seal(attempt, diagnostic)
    result = read(attempt / "result.json")
    if result.get("case_id") != case_id or result.get("provenance_kind") != "native" or result.get("diagnostic_fixture") is not diagnostic:
        raise ValueError("Native result provenance differs")
    verify_physical(result, attempt)
    sources = audit_sources(attempt, case_id)
    frames = sources["original_frame_count"]
    if seal.get("frames") != frames:
        raise ValueError("Sealed original frame count differs")
    review_hash = verify_review(attempt, case_id, pixel_review, frames)
    media.audit(attempt / "raw.mkv", frames, mapping_sha256=sha(attempt / "video_frames.jsonl"))
    receipt = {"format": "worker-c144550-delivery-audit", "case_id": case_id,
               "passed": not diagnostic, "diagnostic_fixture": diagnostic,
               "checks": {key: True for key in CHECKS}, "frames": frames,
               "source_audit": sources, "pixel_review_sha256": review_hash,
               "capture_seal_sha256": sha(attempt / "capture-seal.json"),
               "owner_release_sha256": sha(attempt / "owner-release.json"),
               "physical_acceptance_claimed": False, "auditor_sha256": sha(__file__)}
    output = Path(output).resolve()
    if output.name == "result.json" or attempt not in output.parents or output.exists():
        raise ValueError("Audit receipt must be a new separate file within attempt")
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--pixel-review", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--diagnostic", action="store_true")
    arguments = parser.parse_args()
    print(json.dumps(audit(arguments.attempt, arguments.case, arguments.pixel_review,
                           arguments.output, arguments.diagnostic), sort_keys=True))
