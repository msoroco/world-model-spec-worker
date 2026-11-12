"""Read-only original-source boundary for local C10014 delivery review.

This script cannot accept a CPU fixture. The local adopter supplies a sealed
Native attempt, operator release receipt, saved processing, full decode receipt,
and source-bound review of actual source-camera pixels before acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
VIEW_SUBJECTS = {
    "overview": {"vehicle_body", "driveway_entrance"},
    "approach": {"vehicle_body", "alley_approach"},
    "reference_corner": {"vehicle_body", "driveway_entrance"},
    "driver_reference": {"driveway_entrance", "driver_view"},
}
ORIGINALS = ("trace.jsonl", "capture/evidence.jsonl", "video_frames.jsonl",
             "native_samples.jsonl", "body_history.jsonl", "capture/manifest.json",
             "road_geometry.json")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    require(path.is_file(), "Missing original source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def check_original_rows(attempt: Path, expected_frames: int) -> dict:
    """Independently join Native body, trace, evidence, and camera map rows."""
    sources = {name: rows(attempt / name) for name in ORIGINALS[:5]}
    require(all(len(source) == expected_frames for source in sources.values()),
            "Missing original Native body/frame rows")
    trace, evidence, mapping, motion, body = (sources[name] for name in ORIGINALS[:5])
    previous_frame, previous_time = -1, -math.inf
    for index, (t, e, m, n, b) in enumerate(zip(trace, evidence, mapping, motion, body)):
        frame, time_s = m.get("native_frame"), m.get("time_s")
        require(type(frame) is int and frame > previous_frame and
                type(time_s) in (int, float) and math.isfinite(time_s) and
                time_s > previous_time and m.get("video_frame") == index and
                m.get("carla_frame") == frame and
                t.get("frame") == e.get("original_frame") ==
                n.get("native_frame") == b.get("frame") == frame,
                "Original Native frame join differs")
        require(all(type(row.get(key)) in (int, float) and
                    abs(row[key] - time_s) <= 1e-4
                    for row, key in ((t, "time_s"), (e, "recording_time_s"),
                                     (n, "time_s"), (b, "time_s"))),
                "Original Native timestamp join differs")
        require(not any(row.get("synthetic_diagnostic") is True
                        for row in (t, e, n, b)) and
                n.get("speed_provenance") != "synthetic_native_sample" and
                t.get("speed_provenance") != "synthetic_native_sample" and
                e.get("ego", {}).get("speed_provenance") != "synthetic_native_sample",
                "Synthetic diagnostic cannot establish original Native motion")
        vertices = n.get("native_body_xy_m")
        require(isinstance(vertices, list) and len(vertices) == 4 and
                all(isinstance(v, list) and len(v) == 2 and
                    all(type(x) in (int, float) and math.isfinite(x) for x in v)
                    for v in vertices) and
                type(n.get("speed_mps")) in (int, float) and
                math.isfinite(n["speed_mps"]) and n["speed_mps"] >= 0,
                "Original Native body or velocity missing")
        captured = e.get("ego", {}).get("body_vertices_m")
        historical = b.get("body_vertices_m")
        require(isinstance(captured, list) and isinstance(historical, list) and
                len(captured) >= 4 and len(historical) >= 4 and
                {(round(v[0], 5), round(v[1], 5)) for v in captured} ==
                {(round(v[0], 5), round(v[1], 5)) for v in historical} ==
                {(round(v[0], 5), round(v[1], 5)) for v in vertices},
                "Original Native body/evidence footprint differs")
        previous_frame, previous_time = frame, time_s
    return {"frames": expected_frames, "first_frame": mapping[0]["native_frame"],
            "last_frame": mapping[-1]["native_frame"],
            "frame_map_sha256": sha(attempt / "video_frames.jsonl")}


def check_physical_result(result: dict, case_id: str) -> None:
    checks = result.get("physical_checks", {})
    require(result.get("case_id") == case_id and
            result.get("provenance_kind") == "native" and
            result.get("accepted") is False and
            result.get("legal_verdict_claimed") is False and
            result.get("maneuver_completed") is True and
            result.get("setup_confirmed") is False and
            checks.get("setup", {}).get("status") == "unverified" and
            checks["setup"].get("sources") and
            all(checks.get(name, {}).get("status") == "met" and
                checks[name].get("sources") for name in ("target", "maneuver", "attempt")),
            "Physical completion lacks original measured support")


def check_native_boundary(attempt: Path, saved: Path, owner_receipt: Path,
                          case_id: str, construction_sha256: str) -> dict:
    """Reject absent closure, changed original bytes, and derived false success."""
    attempt, saved = attempt.resolve(), saved.resolve()
    require((attempt / "capture-seal.json").is_file(), "Missing sealed Native capture")
    seal = read(attempt / "capture-seal.json")
    require(seal.get("format") == "worker-sealed-capture" and
            seal.get("provenance_kind") == "native" and
            seal.get("diagnostic_fixture") is False and
            seal.get("physical_acceptance_claimed") is False and
            seal.get("frames") == 480 and
            seal.get("events") == ["capture_finished", "encoders_closed", "restoration_verified"] and
            seal.get("restoration", {}).get("restored") is True and
            set(seal.get("encoder_exit_codes", {})) == set(CAMERAS) and
            all(code == 0 for code in seal["encoder_exit_codes"].values()) and
            seal.get("native_revision", {}).get("construction_sha256") == construction_sha256 and
            seal["native_revision"].get("runner_sha256") == sha(attempt / "runner.py"),
            "Native capture seal or lifecycle incomplete")
    require(set(ORIGINALS + tuple(name + ".mkv" for name in CAMERAS)) <=
            set(seal.get("sources", {})), "Sealed original source inventory incomplete")
    for name, checksum in seal["sources"].items():
        source = (attempt / name).resolve()
        require(attempt in source.parents and source.is_file() and sha(source) == checksum,
                "Sealed original source changed: " + name)
    capture = read(attempt / "capture/manifest.json")
    require(capture.get("extraction_confirmed") is True and
            capture.get("frames") == 480 and
            capture.get("synthetic_diagnostic") is not True,
            "Native extraction missing or synthetic")
    exit_record = read(attempt / "native-exit.json")
    require(exit_record.get("event") == "native_exit" and
            exit_record.get("capture_seal_sha256") == sha(attempt / "capture-seal.json") and
            exit_record.get("native_revision") == seal["native_revision"],
            "Native exit differs from sealed capture")
    owner = read(owner_receipt)
    require(owner.get("event") == "owner_released" and
            owner.get("operator_attested") is True and
            owner.get("native_exit_sha256") == sha(attempt / "native-exit.json") and
            owner.get("native_construction_sha256") == construction_sha256,
            "Operator owner release absent or stale")
    original = check_original_rows(attempt, 480)
    processing = read(saved / "processing.json")
    require(processing.get("case_id") == case_id and
            processing.get("passed") is True and
            processing.get("recorded_only") is True and
            processing.get("missing_evidence") is False and
            processing.get("native_revision", {}).get("construction_sha256") == construction_sha256,
            "Saved processing lacks original Native evidence")
    for name in ORIGINALS + tuple(camera + ".mkv" for camera in CAMERAS):
        require(processing.get("original_source_hashes", {}).get(name) == sha(attempt / name),
                "Saved processing changed original source: " + name)
    result_path = Path(processing["result"]).resolve()
    require(saved in result_path.parents and result_path.is_file(),
            "Saved result escapes selected processing version")
    result = read(result_path)
    check_physical_result(result,case_id)
    return {**original, "case_id": case_id, "result_sha256": sha(result_path),
            "capture_seal_sha256": sha(attempt / "capture-seal.json"),
            "owner_release_sha256": sha(owner_receipt),
            "physical_completion": "measured; legal blocking judgment remains separate"}


def check_pixel_review(review_path: Path, case_id: str, attempt: Path,
                       primary_video: Path, *, test_shape: bool = False) -> dict:
    """Require independent, byte-bound review of visible body and entrance."""
    review = read(review_path)
    require(review.get("format") == "c10014-original-source-pixel-review" and
            review.get("case_id") == case_id and review.get("frames") == 480 and
            review.get("reviewer") and review.get("method") and
            review.get("source_kind") == ("source_shaped_unit_test" if test_shape
                                          else "original_native_camera_pixels") and
            review.get("primary_sha256") == sha(primary_video),
            "Actual pixel review missing or for another source")
    views = review.get("views", {})
    require(set(views) == set(CAMERAS), "Pixel review omits a source camera")
    for name in CAMERAS:
        item = views[name]
        require(item.get("video_sha256") == sha(attempt / (name + ".mkv")) and
                VIEW_SUBJECTS[name] <= set(item.get("subjects_visible", [])) and
                type(item.get("reviewed_stationary_frames")) is int and
                item["reviewed_stationary_frames"] >= 40 and
                item.get("limitations") is not None,
                "Actual source pixels or stationary interval unreviewed: " + name)
    return review


def check_access_review(review_path: Path, case_id: str, attempt: Path,
                        *, test_shape: bool = False) -> dict:
    """Bind an independent property-access designation to the Native map bytes."""
    review = read(review_path)
    geometry = read(attempt / "road_geometry.json")
    require(review.get("format") == "c10014-original-access-review" and
            review.get("case_id") == case_id and
            review.get("source_kind") == ("source_shaped_unit_test" if test_shape
                                          else "original_native_map_and_property_records") and
            review.get("reviewer") and review.get("method") and
            review.get("property_access_id") and
            review.get("road_geometry_sha256") == sha(attempt / "road_geometry.json") and
            review.get("native_map_sha256") == geometry.get("native_map_sha256") and
            all(review.get(key) is True for key in
                ("alley_design_confirmed", "abutting_property_access_confirmed",
                 "entrance_boundary_confirmed")),
            "Original alley/abutting-property access review absent or unbound")
    source = review.get("property_source", {})
    path = Path(source.get("path", ""))
    require(path.is_file() and source.get("sha256") == sha(path),
            "Independent property-access source missing or changed")
    return review


def audit_complete(attempt: Path, saved: Path, owner_receipt: Path,
                   case_id: str, construction_sha256: str, pixel_review: Path,
                   access_review: Path,
                   primary_video: Path, core_trace: Path, decode_dir: Path,
                   job_id: str, attempt_number: int, recording_id: str) -> dict:
    """Produce a local acceptance candidate only after every independent check."""
    attempt, primary_video, core_trace = (path.resolve() for path in
                                          (attempt, primary_video, core_trace))
    boundary = check_native_boundary(attempt, saved, owner_receipt,
                                     case_id, construction_sha256)
    require(primary_video.is_file() and core_trace.is_file() and
            attempt in primary_video.parents and attempt in core_trace.parents,
            "Primary video/Core trace must be promoted with the exact attempt")
    result_path = attempt / "result.json"
    require(result_path.is_file() and sha(result_path) == boundary["result_sha256"],
            "Promoted Native result differs from saved processing")
    scenes = read(core_trace).get("scenes", [])
    mapping = rows(attempt / "video_frames.jsonl")
    require(len(scenes) == len(mapping) == 480 and
            all(scene.get("t") == round(frame["time_s"] * 1000)
                for scene, frame in zip(scenes, mapping)),
            "Core trace does not join original Native frame map")
    review = check_pixel_review(pixel_review, case_id, attempt, primary_video)
    access = check_access_review(access_review, case_id, attempt)
    decode_dir.mkdir(parents=True, exist_ok=True)
    from scenario_pipeline.worker_exchange.media import audit as decode
    mapping_hash = sha(attempt / "video_frames.jsonl")
    for name in CAMERAS:
        decode(attempt / (name + ".mkv"), 480,
               mapping_sha256=mapping_hash, receipt=decode_dir / (name + ".json"))
    primary_receipt = decode_dir / "primary.json"
    primary = decode(primary_video, 480, mapping_sha256=mapping_hash,
                     receipt=primary_receipt)
    return {
        "format": "worker-delivery-audit", "passed": True,
        "attempt_path": str(attempt), "saved_path": str(saved.resolve()),
        "owner_receipt_path": str(owner_receipt.resolve()),
        "owner_receipt_sha256": sha(owner_receipt),
        "case_id": case_id, "job_id": job_id, "attempt": attempt_number,
        "recording_id": recording_id, "frames": 480,
        "source_result_sha256": sha(result_path),
        "video": primary_video.relative_to(attempt).as_posix(),
        "video_sha256": sha(primary_video),
        "trace": core_trace.relative_to(attempt).as_posix(),
        "trace_sha256": sha(core_trace),
        "checks": {key: True for key in
                   ("native_source", "all_participants", "time_join",
                    "full_video_decode", "actual_pixels", "physical_completion")},
        "auditor_path": str(Path(__file__).resolve()),
        "auditor_sha256": sha(Path(__file__)),
        "source_decode_receipt_path": str(primary_receipt.resolve()),
        "source_decode_receipt_sha256": sha(primary_receipt),
        "source_decode_auditor_sha256": primary["auditor_sha256"],
        "source_camera_decode_receipts": {
            name: {"path": str((decode_dir / (name + ".json")).resolve()),
                   "sha256": sha(decode_dir / (name + ".json"))}
            for name in CAMERAS},
        "pixel_review_path": str(pixel_review.resolve()),
        "pixel_review_sha256": sha(pixel_review),
        "access_review_path": str(access_review.resolve()),
        "access_review_sha256": sha(access_review),
        "property_access_id": access["property_access_id"],
        "source_camera_sha256": {name: sha(attempt / (name + ".mkv"))
                                 for name in CAMERAS},
        "native_boundary": boundary,
        "reviewer": review["reviewer"],
        "legal_blocking_verdict_claimed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--saved", type=Path, required=True)
    parser.add_argument("--owner-receipt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--construction-sha256", required=True)
    parser.add_argument("--complete", action="store_true")
    parser.add_argument("--pixel-review", type=Path)
    parser.add_argument("--access-review", type=Path)
    parser.add_argument("--primary-video", type=Path)
    parser.add_argument("--core-trace", type=Path)
    parser.add_argument("--decode-dir", type=Path)
    parser.add_argument("--job-id")
    parser.add_argument("--attempt-number", type=int)
    parser.add_argument("--recording-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.complete:
        require(all((args.pixel_review, args.access_review,
                     args.primary_video, args.core_trace,
                     args.decode_dir, args.job_id, args.attempt_number,
                     args.recording_id, args.output)),
                "Complete audit needs local original review, decode and exact job binding")
        receipt = audit_complete(args.attempt, args.saved, args.owner_receipt,
            args.case, args.construction_sha256, args.pixel_review,
            args.access_review,
            args.primary_video, args.core_trace, args.decode_dir, args.job_id,
            args.attempt_number, args.recording_id)
        require(not args.output.exists(), "Retain previous independent audit")
        args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    else:
        receipt = check_native_boundary(args.attempt, args.saved,
            args.owner_receipt, args.case, args.construction_sha256)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
