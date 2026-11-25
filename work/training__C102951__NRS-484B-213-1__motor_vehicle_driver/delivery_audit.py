"""Independent original-source delivery audit for left-of-center passing."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

PREFIX = "training__C102951__NRS-484B-213-1__motor_vehicle_driver__"
CASES = tuple(PREFIX + str(distance) for distance in (70, 120, 170))
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode", "actual_pixels", "physical_completion")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def audit(case, attempt, saved, pixel_review, output):
    require(case in CASES, "Select exact passing case")
    attempt, saved = Path(attempt).resolve(), Path(saved).resolve()
    require(attempt.is_dir() and saved.is_dir(), "Original attempt or saved processing absent")
    provenance = read(attempt / "acquisition-provenance.json")
    seal = read(attempt / "capture-seal.json")
    require(provenance.get("provenance_kind") == "original_native" and
            provenance.get("diagnostic_fixture") is False and
            seal.get("diagnostic_fixture") is False,
            "Synthetic fixture cannot establish original Native delivery")
    require(seal.get("format") == "worker-sealed-capture" and
            seal.get("frames") == 600 and
            seal.get("events") == ["capture_finished", "encoders_closed", "restoration_verified"] and
            seal.get("restoration", {}).get("restored") is True and
            all(seal.get("encoder_exit_codes", {}).get(camera) == 0 for camera in CAMERAS),
            "Original Native closure incomplete")
    for name, expected in seal.get("sources", {}).items():
        require(sha(attempt / name) == expected, "Sealed Native source changed: " + name)
    native_exit = read(attempt / "native-exit.json")
    owner = read(attempt / "owner-release.json")
    require(native_exit.get("capture_seal_sha256") == sha(attempt / "capture-seal.json") and
            owner.get("native_exit_sha256") == sha(attempt / "native-exit.json") and
            owner.get("event") == "owner_released", "Saved processing precedes Native exit or owner release")
    processing = read(saved / "processing.json")
    require(processing.get("case_id") == case and processing.get("passed") is True and
            processing.get("recorded_only") is True and processing.get("originals_preserved") is True and
            processing.get("timestamp_joins", {}).get("frames") == 600 and
            processing.get("missing_evidence") is False,
            "Saved-only processing lacks complete original joins")
    result_path = Path(processing["result"]).resolve()
    result = read(result_path)
    require(result.get("case_id") == case and result.get("provenance_kind") == "native" and
            result.get("diagnostic_fixture") is not True and
            result.get("legal_acceptance_claimed") is not True and
            result.get("legal_verdict_claimed") is False,
            "Original saved analysis or provenance missing")
    native, trace, mapping = (rows(attempt / name) for name in
                              ("native-observed.jsonl", "trace.jsonl", "video_frames.jsonl"))
    require(len(native) == len(trace) == len(mapping) == 600, "Original 600-frame join incomplete")
    for i, (n, t, m) in enumerate(zip(native, trace, mapping)):
        frame = m.get("carla_frame")
        require(frame == n.get("native_frame") == t.get("frame") and
                m.get("video_frame") == i and
                abs(m.get("time_s") - n.get("time_s")) < 1e-4 and
                abs(m.get("time_s") - t.get("time_s")) < 1e-4,
                "Original Native frame/time join differs")
        require(all(isinstance(n.get(role), dict) and n[role].get("body_native_xyz_m")
                    for role in ("ego", "overtaken", "oncoming")),
                "Original passing participant missing")
    ego = [n["ego"]["center_native_xyz_m"] for n in native]
    overtaken = [n["overtaken"]["center_native_xyz_m"] for n in native]
    relative_x = [other[0] - subject[0] for subject, other in zip(ego, overtaken)]
    lateral = [p[1] for p in ego]
    require(relative_x[0] > 0 and relative_x[-1] < 0 and
            max(lateral) - min(lateral) >= 1.0 and
            abs(lateral[-1] - lateral[0]) < 1.0,
            "Original physical passing motion incomplete")
    review = read(pixel_review)
    require(review.get("case_id") == case and review.get("source_kind") == "original_native_pixels" and
            review.get("reviewer") and review.get("method") and
            review.get("legal_verdict_claimed") is False and
            set(review.get("views", {})) == set(CAMERAS),
            "Independent original pixel review missing")
    for camera in CAMERAS:
        item = review["views"][camera]
        require(item.get("video_sha256") == sha(attempt / (camera + ".mkv")) and
                item.get("reviewed_frames", 0) > 0 and
                item.get("ego_visible") is True and
                item.get("overtaken_visible") is True and
                item.get("oncoming_visibility_assessed") is True and
                item.get("crest_visibility_assessed") is True,
                "Original camera pixels unreviewed: " + camera)
    from worker_exchange.media import audit as decode
    decode_dir = Path(output).resolve().parent / (case + "-source-decode")
    decode_dir.mkdir(parents=True, exist_ok=True)
    receipts = {camera: decode(attempt / (camera + ".mkv"), 600,
                    receipt=decode_dir / (camera + ".json"),
                    mapping_sha256=sha(attempt / "video_frames.jsonl")) for camera in CAMERAS}
    receipt = {
        "format": "worker-delivery-audit", "passed": True, "case_id": case,
        "frames": 600, "checks": {check: True for check in CHECKS},
        "attempt_path": str(attempt), "saved_path": str(saved),
        "source_result_sha256": sha(result_path), "capture_seal_sha256": sha(attempt / "capture-seal.json"),
        "owner_receipt_path": str(attempt / "owner-release.json"),
        "owner_receipt_sha256": sha(attempt / "owner-release.json"),
        "video": "overview.mkv", "video_sha256": sha(attempt / "overview.mkv"),
        "trace": "trace.jsonl", "trace_sha256": sha(attempt / "trace.jsonl"),
        "source_decode_receipt_path": str(decode_dir / "overview.json"),
        "source_decode_receipt_sha256": sha(decode_dir / "overview.json"),
        "source_decode_auditor_sha256": receipts["overview"]["auditor_sha256"],
        "pixel_review_sha256": sha(pixel_review), "legal_verdict_claimed": False,
        "physical_method": "original source whole-pass order and lateral return; engineering evidence only",
    }
    Path(output).write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def selftest(case, negative):
    require(case in CASES, "Select exact passing case")
    require(len(CAMERAS) == 4 and len(CHECKS) == 6, "Incomplete audit inventory")
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    require(".runtime-work" in scratch.parts, "Audit fixture scratch must remain under .runtime-work")
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temp:
        attempt, saved = Path(temp) / "attempt", Path(temp) / "saved"
        attempt.mkdir()
        saved.mkdir()
        (attempt / "acquisition-provenance.json").write_text(json.dumps({"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
        (attempt / "capture-seal.json").write_text(json.dumps({"format": "worker-sealed-capture", "diagnostic_fixture": True}) + "\n")
        try:
            audit(case, attempt, saved, "unused", Path(temp) / "unused.json")
        except ValueError as error:
            require(str(error) == "Synthetic fixture cannot establish original Native delivery", "Synthetic source rejected for another reason")
            if negative:
                raise
        else:
            raise AssertionError("Synthetic source passed original Native delivery")
    print("PASS exact passing case, independent six-check inventory and synthetic rejection boundary")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--negative-fixture", action="store_true")
    parser.add_argument("--attempt")
    parser.add_argument("--saved")
    parser.add_argument("--pixel-review")
    parser.add_argument("--output")
    args = parser.parse_args()
    selftest(args.case, args.negative_fixture) if args.selftest else audit(args.case, args.attempt, args.saved, args.pixel_review, args.output)
