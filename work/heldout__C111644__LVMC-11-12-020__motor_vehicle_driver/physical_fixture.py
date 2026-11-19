"""Exercise turn-completion decisions on retained synthetic source packets.

The input is a CPU diagnostic attempt. None of these outcomes represents a
Native capture, actual camera pixels, or physical/legal acceptance.
"""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

from turn_marking import analyze_original_sources


KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")
REQUIRED = ("turn_source_receipt.json", "turn_indication_original.json",
            "turn_indication_readback_original.json", "turn_route_plan.json",
            "turn_body_original.jsonl", "trace.jsonl", "video_frames.jsonl",
            "overview.mkv", "approach.mkv", "reference_corner.mkv",
            "driver_reference.mkv", "overview-frames.jsonl",
            "approach-frames.jsonl", "reference_corner-frames.jsonl",
            "driver_reference-frames.jsonl")


def _rows(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]


def run(case_id: str, attempt: Path, kind: str) -> dict:
    if kind not in KINDS:
        raise ValueError("Unknown fixture kind")
    attempt = attempt.resolve()
    if not all((attempt / name).is_file() for name in REQUIRED):
        raise ValueError("Incomplete retained source packet")
    source_hashes = {name: sha256((attempt / name).read_bytes()).hexdigest()
                     for name in REQUIRED if name != "turn_source_receipt.json"}
    if kind == "missing_evidence":
        # Symlink into a disposable attempt so the original packet stays intact.
        with TemporaryDirectory(prefix="turn-missing-source-") as temp:
            temp_path = Path(temp)
            for name in REQUIRED:
                if name != "turn_body_original.jsonl":
                    (temp_path / name).symlink_to(attempt / name)
            try:
                analyze_original_sources(temp_path)
            except ValueError as error:
                if "Missing required source: turn_body_original.jsonl" not in str(error):
                    raise
            else:
                raise ValueError("Missing original turn body was accepted")
        source_hashes.pop("turn_body_original.jsonl")
        status = "unverified"
        observed = {}
        missing = ["turn_body_original.jsonl"]
        method = "Source verification rejects a deleted original body packet"
    else:
        analysis = analyze_original_sources(attempt)
        if analysis["case_id"] != case_id:
            raise ValueError("Synthetic attempt case identity differs")
        body = _rows(attempt / "turn_body_original.jsonl")
        samples = analysis["samples"]
        if len(body) != len(samples) or len(samples) < 3:
            raise ValueError("Original body and measured samples differ")
        # Incomplete capture is a two-frame replay window of this same source
        # packet. It cannot satisfy the engineering 4 m / 60 degree criterion.
        window = len(samples) if kind == "complete_motion" else 2
        distance = float(samples[window - 1]["path_length_m"])
        angle = abs(float(body[window - 1]["subject"]["heading_deg"])
                    - float(body[0]["subject"]["heading_deg"]))
        status = "met" if distance >= 4.0 and 60.0 <= angle <= 120.0 else "not_met"
        observed = {"source_frame_count": window,
                    "sampled_body_path_m": distance,
                    "observed_heading_change_deg": angle,
                    "engineering_criterion_not_legal": True}
        missing = []
        method = ("Source-joined original turn packet measured over a synthetic "
                  f"{window}-frame replay window; 4 m and 60-120 degree "
                  "engineering fixture criterion only")
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    if status != expected:
        raise ValueError(f"{kind} produced {status}, expected {expected}")
    return {"case_id": case_id, "fixture_kind": kind,
            "diagnostic_fixture": True, "actual_native_capture": False,
            "provenance_kind": "synthetic_fixture",
            "provenance_note": "CPU replay of a synthetic source packet; no Native acquisition",
            "physical_checks": {"maneuver": {"status": status, "method": method,
                                              "sources": source_hashes,
                                              "missing_evidence": missing}},
            "maneuver_completed": status == "met",
            "realized_observables": observed,
            "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}


def lifecycle(case_id: str) -> dict:
    """Prove ordered ownership on a fresh current-manifest synthetic packet."""
    repo = Path(__file__).resolve().parents[2]
    manifest = Path(__file__).resolve().parent / "execution-manifest.json"
    entry = next((x for x in json.loads(manifest.read_text())["cases"]
                  if x["case_id"] == case_id), None)
    if entry is None:
        raise ValueError("Unknown exact turn case")
    sys.path.insert(0, str(repo / "runtime"))
    sys.path.insert(0, str(repo / "runtime/scenario_pipeline"))
    from worker_exchange.fixture_recipe import materialize as make_fixture
    from worker_exchange.runtime_cli import materialize as make_attempt
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import (copy_sources, record_native_exit,
                                                   acknowledge_owner_release,
                                                   run as process_saved)
    validator = repo / ".runtime-work/c125714-validator/.lake/build/bin/adapterCheck"
    with TemporaryDirectory(prefix="c111644-lifecycle-", dir=repo / ".runtime-work") as temp:
        base = Path(temp)
        make_fixture(repo, repo / entry["fixture_recipe"], base / "fixture")
        make_attempt(manifest, case_id, base / "attempt")
        copy_sources(base / "fixture", base / "attempt")
        attempt = base / "attempt"
        (attempt / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "fixture_scope": "synthetic lifecycle protocol only"}) + "\n")
        cameras = ("overview", "approach", "reference_corner", "driver_reference")
        frames = len((attempt / "video_frames.jsonl").read_text().splitlines())
        seal = seal_capture(attempt, frames=frames, restoration={"restored": True},
                            errors=[], encoder_exit_codes={name: 0 for name in cameras},
                            context={"fixture_scope": "synthetic lifecycle protocol only"})
        events = ["capture_finished", "encoders_closed", "restoration_verified",
                  "native_exit", "owner_released", "saved_processing_started"]
        if seal.get("events") != events[:3] or seal.get("diagnostic_fixture") is not True:
            raise ValueError("Synthetic capture closure not sealed in order")
        try:
            process_saved(manifest, case_id, attempt, base / "premature", repo / "runtime/library",
                          validator)
        except (ValueError, RuntimeError, FileNotFoundError) as error:
            if not any(term in str(error).lower() for term in
                       ("native-exit", "native exit", "owner", "release", "lifecycle")):
                raise
        else:
            raise ValueError("Saved processing before owner release was accepted")
        if record_native_exit(attempt).get("event") != events[3]:
            raise ValueError("Native exit event missing")
        owner = base / "owner-release.json"
        if acknowledge_owner_release(attempt, owner, True).get("event") != events[4]:
            raise ValueError("Owner release event missing")
        saved = process_saved(manifest, case_id, attempt, base / "saved", repo / "runtime/library",
                              validator, owner_receipt=owner)
        if (saved.get("passed") is not True or saved.get("originals_preserved") is not True
                or saved.get("missing_evidence") is not False):
            raise ValueError("Post-release saved processing did not preserve sources")
        return {"case_id": case_id, "events": events, "exit_code": 0,
                "premature_processing_rejected": True,
                "post_release_saved_passed": True,
                "provenance_kind": "synthetic_fixture",
                "native_motion_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--kind", choices=KINDS)
    parser.add_argument("--lifecycle", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.lifecycle:
        if args.kind or args.attempt:
            raise ValueError("Lifecycle uses a fresh current-manifest packet")
        result = lifecycle(args.case)
    else:
        if args.kind is None or args.attempt is None:
            raise ValueError("Physical fixture needs kind and attempt")
        result = run(args.case, args.attempt, args.kind)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    if args.lifecycle:
        print(" ".join(result["events"]))
        print(args.case, "synthetic_lifecycle_only", "saved_processing_passed")
    else:
        print(args.case, args.kind, result["physical_checks"]["maneuver"]["status"],
              "synthetic_fixture_only")
