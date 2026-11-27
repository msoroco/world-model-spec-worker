"""Independent original-source emergency-lane delivery audit.

CPU selftests inventory the checks and reject a synthetic fixture. Original
delivery requires sealed Native sources, source-joined activation and full
camera decode. No diagnostic fixture establishes physical or legal acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from saved_measure import VIDEOS, measure_saved, rows


AID = "training__C405647__NRS-484B-267-2b__motor_vehicle_driver"
CASES = {AID + f"__probe_0{i}" for i in range(1, 6)}
VIEWS = tuple(name.removesuffix(".mkv") for name in VIDEOS)
CHECKS = ("native_source", "all_participants", "time_join",
          "full_video_decode", "actual_pixels", "physical_completion")


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect_sources(case, attempt):
    config = read(attempt / "config.json")
    require(config.get("case_id") == case, "Exact original emergency case differs")
    measurements = measure_saved(attempt, case, diagnostic=False)['measurement']
    native = rows(attempt / "emergency-native.jsonl")
    mapping = rows(attempt / "video_frames.jsonl")
    require(len(native) == len(mapping) == 600, "Original 600-frame source join incomplete")
    for row, frame in zip(native, mapping):
        require(set(frame.get("camera_native_frames", {})) == set(VIEWS) and
                all(frame["camera_native_frames"][view] == row["native_frame"]
                    for view in VIEWS), "Original camera frame joins differ")
    suffix = case[-2:]
    require(measurements['first_passing_frame'] > measurements['first_approach_frame'],
            'Original approach and passing sequence unobserved')
    if suffix == "03":
        require(measurements['qualifying_role'] == 'official_regulatory',
                'Original official regulatory role unverified')
    if suffix == "04":
        require(measurements['activation_mode'] == 'visible_hand_signal',
                "Original visible driver preparation missing")
    if suffix == "05":
        require(any(s != 'none' for s in measurements['officer_direction_states']),
                "Original officer direction missing")
    return {'first_approach_frame': measurements['first_approach_frame'],
            'first_passing_frame': measurements['first_passing_frame'],
            'qualifying_role': measurements['qualifying_role'],
            'speed_mps': measurements['ego_speed_at_first_pass_mps'],
            'surface_gap_m': measurements['minimum_passing_surface_gap_m'],
            'officer_override_applies': None, 'legal_result': None}


def audit(case, attempt, saved, output):
    require(case in CASES, "Select exact emergency-lane case")
    attempt, saved, output = Path(attempt).resolve(), Path(saved).resolve(), Path(output).resolve()
    provenance = read(attempt / "acquisition-provenance.json")
    seal = read(attempt / "capture-seal.json")
    require(provenance.get("provenance_kind") in ("native", "original_native") and
            provenance.get("diagnostic_fixture") is False and
            seal.get("provenance_kind") == "native" and
            seal.get("diagnostic_fixture") is False,
            "Synthetic fixture cannot establish original Native delivery")
    require(seal.get("format") == "worker-sealed-capture" and seal.get("frames") == 600 and
            seal.get("events") == ["capture_finished", "encoders_closed",
                                   "restoration_verified"] and
            seal.get("restoration", {}).get("restored") is True and
            all(seal.get("encoder_exit_codes", {}).get(view) == 0 for view in VIEWS),
            "Original Native capture closure incomplete")
    for name, checksum in seal.get("sources", {}).items():
        require(sha(attempt / name) == checksum,
                "Sealed original source changed: " + name)
    exit_record, owner = read(attempt / "native-exit.json"), read(attempt / "owner-release.json")
    require(exit_record.get("capture_seal_sha256") == sha(attempt / "capture-seal.json") and
            owner.get("native_exit_sha256") == sha(attempt / "native-exit.json") and
            owner.get("event") == "owner_released",
            "Saved processing precedes Native exit or owner release")
    processing = read(saved / "processing.json")
    require(processing.get("case_id") == case and processing.get("passed") is True and
            processing.get("recorded_only") is True and
            processing.get("originals_preserved") is True and
            processing.get("missing_evidence") is False and
            processing.get("timestamp_joins", {}).get("frames") == 600,
            "Saved-only original processing incomplete")
    result = read(Path(processing["result"]).resolve())
    require(result.get("case_id") == case and
            result.get("provenance_kind") in ("native", "original_native") and
            result.get("diagnostic_fixture") is not True,
            "Saved original result provenance differs")
    physical = inspect_sources(case, attempt)
    from worker_exchange.media import audit as decode
    decode_dir = output.parent / (case + "-source-decode")
    decode_dir.mkdir(parents=True, exist_ok=True)
    receipts = {view: decode(attempt / (view + ".mkv"), 600,
                             receipt=decode_dir / (view + ".json"),
                             mapping_sha256=sha(attempt / "video_frames.jsonl"))
                for view in VIEWS}
    core = Path(processing["version"]) / "converted/trace.json"
    require(core.is_file() and len(read(core).get("scenes", [])) == 600,
            "Saved original Core scene sequence unavailable")
    receipt = {"format": "worker-delivery-audit", "passed": True,
               "case_id": case, "frames": 600,
               "checks": {name: True for name in CHECKS},
               "source_result_sha256": processing["result_sha256"],
               "video": "overview.mkv", "video_sha256": sha(attempt / "overview.mkv"),
               "trace": str(core), "trace_sha256": sha(core),
               "source_decode_receipt_path": str(decode_dir / "overview.json"),
               "source_decode_receipt_sha256": sha(decode_dir / "overview.json"),
               "source_decode_auditor_sha256": receipts["overview"]["auditor_sha256"],
               "auditor_path": str(Path(__file__).resolve()),
               "auditor_sha256": sha(__file__),
               "physical_observables": physical, "legal_verdict_claimed": False}
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def selftest(case, negative):
    require(case in CASES and len(VIEWS) == 4 and len(CHECKS) == 6,
            "Exact case or independent audit inventory differs")
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    require(".runtime-work" in scratch.parts, "Diagnostic scratch outside .runtime-work")
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temp:
        attempt, saved = Path(temp) / "attempt", Path(temp) / "saved"
        attempt.mkdir(); saved.mkdir()
        (attempt / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
        (attempt / "capture-seal.json").write_text(json.dumps({
            "format": "worker-sealed-capture", "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True}) + "\n")
        try:
            audit(case, attempt, saved, Path(temp) / "audit.json")
        except ValueError as error:
            require(str(error) == "Synthetic fixture cannot establish original Native delivery",
                    "Synthetic fixture rejected for wrong reason")
            if negative:
                raise
        else:
            raise AssertionError("Synthetic fixture passed original delivery")
    print("PASS six original-source checks inventoried; synthetic delivery rejected")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--negative-fixture", action="store_true")
    parser.add_argument("--attempt")
    parser.add_argument("--saved")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.selftest:
        selftest(args.case, args.negative_fixture)
    else:
        print(json.dumps(audit(args.case, args.attempt, args.saved, args.output), sort_keys=True))
