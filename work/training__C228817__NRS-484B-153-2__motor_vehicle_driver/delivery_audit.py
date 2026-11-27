"""Independent original-source audit before exact-case delivery acceptance.

This inspects sealed Native sources, reviewed pixels and saved-only output.
Synthetic fixtures exercise the CPU boundary but cannot pass live acceptance.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


PREFIX = "training__C228817__NRS-484B-153-2__motor_vehicle_driver__probe_"
CASES = {PREFIX + str(n) for n in range(1, 5)}
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def inspect_join(case, attempt, review):
    mapping = rows(attempt / "video_frames.jsonl")
    trace = rows(attempt / "native-door-trace.jsonl")
    require(len(mapping) == len(trace) == 600, "Original door actor/frame join incomplete")
    driver = trace[0]["driver_actor_id"]
    passing = trace[0]["passing_actor_id"]
    walker = trace[0]["pedestrian_actor_id"]
    require(len({driver, passing, walker}) == 3, "Distinct original participants required")
    first = mapping[0]["native_frame"]
    origin = mapping[0]["native_elapsed_s"]
    for i, (frame, actor) in enumerate(zip(mapping, trace)):
        require(frame["video_frame"] == actor["video_frame"] == i and
                frame["native_frame"] == actor["native_frame"] == first + i and
                abs(frame["native_elapsed_s"] - actor["native_elapsed_s"]) < 1e-5 and
                abs(frame["native_elapsed_s"] - origin - i / 20) < 1e-4 and
                actor["driver_actor_id"] == driver and
                actor["passing_actor_id"] == passing and
                actor["pedestrian_actor_id"] == walker,
                "Original participant/time join differs")
        require(actor.get("door_state_observed") is None and
                actor.get("occupancy_delta_observed") is None,
                "Command was mislabeled as observed door or transfer")
    require(review.get("format") == "c228817-door-pixel-review-v1" and
            review.get("case_id") == case and
            review.get("source_kind") == "original_native_pixels" and
            review.get("legal_verdict_claimed") is False,
            "Independent original pixel review missing")
    require(set(review.get("camera_sha256", {})) == set(VIEWS) and
            all(review["camera_sha256"][view] == sha(attempt / (view + ".mkv"))
                for view in VIEWS), "Reviewed camera bytes differ")
    observations = review.get("door_observations", [])
    require(len(observations) == 600 and
            all(row.get("video_frame") == i and type(row.get("door_open")) is bool and
                row.get("source_camera") in VIEWS and row.get("pixel_box_xyxy")
                for i, row in enumerate(observations)),
            "Every source frame needs a reviewed door pixel")
    opened = [i for i, row in enumerate(observations) if row["door_open"]]
    require(opened and opened[0] > 0 and opened[-1] < 599,
            "Observed traffic-side door opening and closing incomplete")
    require(review.get("observed_door_side") == review.get("observed_traffic_side") and
            review.get("observed_door_side") in ("left", "right"),
            "Closest-to-passing-traffic door side unverified")
    events = review.get("transfer_events", [])
    kind = "cargo" if case.endswith(("3", "4")) else "passenger"
    require(events and all(event.get("kind") == kind and
                           event.get("video_frame") in range(opened[0], opened[-1] + 1) and
                           event.get("source_camera") in VIEWS and
                           event.get("pixel_box_xyxy") for event in events),
            "Contemporaneous passenger/cargo transfer pixels missing")
    if kind == "cargo":
        require(trace[0].get("cargo_actor_id") and
                all(event.get("cargo_actor_id_observed") == trace[0]["cargo_actor_id"]
                    for event in events), "Cargo actor identity unreviewed")
    else:
        require(all(event.get("occupancy_delta_observed") in (-1, 1)
                    for event in events), "Passenger occupancy change unreviewed")
    return {"open_frames": len(opened), "open_interval_s": [opened[0] / 20,
            (opened[-1] + 1) / 20], "transfer_events": len(events),
            "traffic_side": review["observed_traffic_side"]}


def audit(case, attempt, saved, output):
    require(case in CASES, "Select exact door case")
    attempt, saved, output = Path(attempt).resolve(), Path(saved).resolve(), Path(output).resolve()
    provenance = read(attempt / "acquisition-provenance.json")
    seal = read(attempt / "capture-seal.json")
    require(provenance.get("provenance_kind") == "original_native" and
            provenance.get("diagnostic_fixture") is False and
            seal.get("provenance_kind") == "native" and
            seal.get("diagnostic_fixture") is False,
            "Synthetic fixture cannot establish original Native delivery")
    require(seal.get("format") == "worker-sealed-capture" and
            seal.get("frames") == 600 and
            seal.get("events") == ["capture_finished", "encoders_closed", "restoration_verified"] and
            seal.get("restoration", {}).get("restored") is True and
            all(seal.get("encoder_exit_codes", {}).get(view) == 0 for view in VIEWS),
            "Original Native capture closure incomplete")
    for name, checksum in seal.get("sources", {}).items():
        require(sha(attempt / name) == checksum, "Sealed original source changed: " + name)
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
    result_path = Path(processing["result"]).resolve()
    result = read(result_path)
    require(result.get("case_id") == case and
            result.get("provenance_kind") == "native" and
            result.get("diagnostic_fixture") is not True and
            result.get("legal_verdict_claimed") is False,
            "Saved result provenance or legal scope differs")
    physical = inspect_join(case, attempt, read(attempt / "door-pixel-review.json"))
    from worker_exchange.media import audit as decode
    decode_dir = output.parent / (case + "-source-decode")
    decode_dir.mkdir(parents=True, exist_ok=True)
    receipts = {view: decode(attempt / (view + ".mkv"), 600,
                             receipt=decode_dir / (view + ".json"),
                             mapping_sha256=sha(attempt / "video_frames.jsonl"))
                for view in VIEWS}
    core = attempt / "converted/trace.json"
    require(core.is_file() and len(read(core).get("scenes", [])) == 600,
            "Original Core scene sequence unavailable for independent delivery")
    receipt = {"format": "worker-delivery-audit", "passed": True, "case_id": case,
               "frames": 600, "checks": {name: True for name in CHECKS},
               "source_result_sha256": sha(attempt / "result.json"),
               "video": "overview.mkv", "video_sha256": sha(attempt / "overview.mkv"),
               "trace": "converted/trace.json", "trace_sha256": sha(core),
               "source_decode_receipt_path": str(decode_dir / "overview.json"),
               "source_decode_receipt_sha256": sha(decode_dir / "overview.json"),
               "source_decode_auditor_sha256": receipts["overview"]["auditor_sha256"],
               "auditor_path": str(Path(__file__).resolve()),
               "auditor_sha256": sha(__file__), "physical_observables": physical,
               "legal_verdict_claimed": False}
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def selftest(case, negative):
    require(case in CASES and len(VIEWS) == 4 and len(CHECKS) == 6,
            "Exact case or independent check inventory differs")
    root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    require(".runtime-work" in root.parts, "Diagnostic scratch outside .runtime-work")
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as temp:
        attempt, saved = Path(temp) / "attempt", Path(temp) / "saved"
        attempt.mkdir()
        saved.mkdir()
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
