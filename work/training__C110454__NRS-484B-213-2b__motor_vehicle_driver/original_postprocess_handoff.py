"""Bind a sealed original Native capture to owner release and saved processing.

This runs only during local import. It never attests release on an operator's
behalf, edits acquisition, or accepts a recording.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next((parent for parent in HERE.parents if (parent / "batch.json").is_file()), None)
if ROOT is None:
    raise RuntimeError("Postprocessing handoff needs the batch repository")
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]
REQUIRED_SOURCES = {"config.json", "construction.json", "runner.py",
                    "acquisition-provenance.json", "native_samples.jsonl",
                    "trace.jsonl", "capture/evidence.jsonl", "video_frames.jsonl",
                    "overview.mkv", "approach.mkv", "reference_corner.mkv",
                    "driver_reference.mkv"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_closure(attempt, owner_receipt, case_id, candidate_id, construction_sha256):
    attempt = Path(attempt).resolve()
    owner_receipt = Path(owner_receipt).resolve()
    require(owner_receipt == attempt / "owner-release.json", "Owner receipt must be retained in original attempt")
    config = read(attempt / "config.json")
    provenance = read(attempt / "acquisition-provenance.json")
    seal_path, exit_path = attempt / "capture-seal.json", attempt / "native-exit.json"
    seal, exited, owner = read(seal_path), read(exit_path), read(owner_receipt)
    require(config.get("case_id") == case_id and config.get("candidate_id") == candidate_id and
            sha(attempt / "construction.json") == construction_sha256,
            "Original case, candidate or construction differs")
    require(provenance.get("provenance_kind") == "native" and
            provenance.get("diagnostic_fixture") is False and
            seal.get("format") == "worker-sealed-capture" and
            seal.get("provenance_kind") == "native" and
            seal.get("diagnostic_fixture") is False and seal.get("frames") == 480 and
            seal.get("events") == EVENTS[:3] and
            seal.get("native_revision") == {"construction_sha256": construction_sha256,
                                            "runner_sha256": sha(attempt / "runner.py")},
            "Original Native capture seal differs")
    sources = seal.get("sources", {})
    require(REQUIRED_SOURCES <= set(sources), "Sealed original source set incomplete")
    for name, digest in sources.items():
        path = (attempt / name).resolve()
        require(attempt in path.parents and path.is_file() and sha(path) == digest,
                "Sealed original source changed: " + name)
    require(exited.get("event") == "native_exit" and
            exited.get("native_process_exit_code") == 0 and
            exited.get("capture_command_failed") is False and
            exited.get("capture_seal_sha256") == sha(seal_path) and
            exited.get("native_revision") == seal["native_revision"],
            "Native exit differs from sealed capture")
    require(owner.get("event") == "owner_released" and
            owner.get("operator_attested") is True and
            owner.get("no_resource_operation_performed") is True and
            owner.get("native_construction_sha256") == construction_sha256 and
            owner.get("native_exit_sha256") == sha(exit_path),
            "Owner release differs from Native exit")
    return {"capture_seal_sha256": sha(seal_path), "native_exit_sha256": sha(exit_path),
            "owner_release_sha256": sha(owner_receipt),
            "construction_sha256": construction_sha256}


def bind_processing(attempt, owner_receipt, processing_path, case_id, candidate_id,
                    construction_sha256):
    closure = verify_closure(attempt, owner_receipt, case_id, candidate_id, construction_sha256)
    processing_path = Path(processing_path).resolve()
    processed = read(processing_path)
    require(processed.get("format") == "worker-saved-processing" and
            processed.get("case_id") == case_id and
            processed.get("candidate_id") == candidate_id and
            processed.get("passed") is True and processed.get("recorded_only") is True and
            processed.get("originals_preserved") is True and
            (processed.get("events") or [None])[0] == "saved_processing_started" and
            processed.get("native_revision", {}).get("construction_sha256") == construction_sha256,
            "Saved processing differs from original Native revision")
    require(all(processed.get("original_source_hashes", {}).get(name) == digest
                for name, digest in read(Path(attempt) / "capture-seal.json")["sources"].items()),
            "Saved processing source inventory differs from capture seal")
    return {"format": "c110454-original-owner-handoff-v1", "case_id": case_id,
            "candidate_id": candidate_id, **closure,
            "processing_sha256": sha(processing_path), "events": EVENTS,
            "original_capture_verified": True, "recording_accepted": False,
            "physical_or_legal_acceptance_claimed": False}


def run(args):
    manifest = read(args.manifest)
    entry = next((e for e in manifest["cases"] if e["case_id"] == args.case), None)
    require(entry is not None, "Unselected original postprocessing case")
    selection = read(Path(args.attempt) / "candidate-selection.json")
    candidate_id = selection["candidate_id"]
    candidate = entry if candidate_id == "primary" else next(
        (c for c in entry["candidates"] if c["id"] == candidate_id), None)
    require(candidate is not None, "Unselected original candidate")
    verify_closure(args.attempt, args.owner_release_receipt, args.case, candidate_id,
                   candidate["construction_sha256"])
    command = [sys.executable, str(ROOT / "runtime.py"), "process-saved",
               "--manifest", str(args.manifest), "--case", args.case,
               "--attempt", str(args.attempt), "--output", str(args.output),
               "--library", str(args.library), "--validator", str(args.validator),
               "--owner-release-receipt", str(args.owner_release_receipt)]
    completed = subprocess.run(command, cwd=ROOT, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(completed.returncode == 0, "Saved processing failed: " + completed.stderr[-1500:])
    receipt = json.loads(completed.stdout)
    processing_path = Path(receipt["version"]) / "processing.json"
    handoff = bind_processing(args.attempt, args.owner_release_receipt, processing_path,
                              args.case, candidate_id, candidate["construction_sha256"])
    handoff_path = processing_path.parent / "owner-handoff.json"
    require(not handoff_path.exists(), "Retain previous owner handoff")
    handoff_path.write_text(json.dumps(handoff, indent=2) + "\n")
    return {"processing": str(processing_path), "owner_handoff": str(handoff_path),
            "owner_handoff_sha256": sha(handoff_path), "recording_accepted": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("manifest", "case", "attempt", "output", "library", "validator",
                 "owner-release-receipt"):
        parser.add_argument("--" + name, required=True)
    print(json.dumps(run(parser.parse_args())))
