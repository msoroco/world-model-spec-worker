"""Prove saved-only processing and actionable feedback for exact bus cases."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
ASSIGNMENT = WORK.name
SCRATCH = REPO / ".runtime-work/c262661-postcapture"
SOURCE = REPO / ".runtime-work/c262661-nov26"
VALIDATOR = REPO / ".runtime-work/c111125-owner/validator/.lake/build/bin/adapterCheck"
EXCLUDE = {"candidate-selection.json", "result.json", "analysis-report.json",
           "compatibility.json", "processing.json", "feedback.json", "traffic_spec",
           "converted", "channels", "event_review.webm", "event_review.json",
           "event_review_encoder.log", "event_review_frames.jsonl", "review_label.txt",
           "review_measured_speed.ass", "review_render.lock", "final-decode.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def prepare_attempt(tag: str, variant: str) -> Path:
    original = SOURCE / f"compat2-{tag}"
    if not original.is_dir():
        raise FileNotFoundError(original)
    target = SCRATCH / f"{tag}-{variant}-attempt"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for path in original.iterdir():
        if path.name in EXCLUDE or path.name.startswith(("source-", "primary", "annotated")):
            continue
        if path.is_dir():
            if path.name not in ("capture", "cameras"):
                continue
            for source in path.rglob("*"):
                if source.is_file():
                    dest = target / source.relative_to(original)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    os.link(source, dest)
        elif path.is_file():
            os.link(path, target / path.name)
    if variant == "missing-source":
        (target / "original-trace.jsonl").unlink()
    return target


def prove(entry: dict, variant: str) -> dict:
    case = entry["case_id"]
    tag = case.rsplit("__", 1)[-1]
    attempt = prepare_attempt(tag, variant)
    output = SCRATCH / f"{tag}-{variant}-output"
    if output.exists():
        shutil.rmtree(output)
    validator = VALIDATOR if variant != "missing-validator" else SCRATCH / "absent-validator"
    command = [sys.executable, str(REPO / "runtime.py"), "process-saved",
               "--manifest", str(WORK / "execution-manifest.json"), "--case", case,
               "--attempt", str(attempt), "--output", str(output),
               "--library", str(REPO / "runtime/library"), "--validator", str(validator)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH), TMPDIR=str(SCRATCH))
    result = subprocess.run(command, cwd=REPO, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=900, check=False)
    log = WORK / f"cpu-post-capture-{tag}-{variant}.log"
    log.write_text(result.stdout.rstrip() + f"\nexit_code={result.returncode}\n")
    version = output / "v0001"
    processing = json.loads((version / "processing.json").read_text()) if (version / "processing.json").is_file() else None
    feedback = json.loads((version / "feedback.json").read_text()) if (version / "feedback.json").is_file() else None
    if variant == "positive":
        assert result.returncode == 0 and processing and processing["recorded_only"]
        assert processing["passed"] and processing["originals_preserved"]
        assert not processing["missing_evidence"] and not processing["physical_acceptance_claimed"]
        assert processing["final_video_checks"]["passed"]
    elif variant == "missing-source":
        assert result.returncode == 0 and processing and processing["recorded_only"]
        assert processing["missing_evidence"] and processing["originals_preserved"]
        assert feedback and feedback["classification"] == "incomplete_or_unavailable_law_evidence"
        assert "Missing required source: original-trace.jsonl" in feedback["error"]
        assert feedback["native_replay_requested"] is False
    else:
        assert result.returncode != 0 and feedback and feedback["recorded_only"]
        assert feedback["native_replay_requested"] is False
        assert feedback["error_type"] == "FileNotFoundError"
    proof = {"exit_code": result.returncode, "log": log.name, "log_sha256": sha(log)}
    if processing:
        proof["processing_sha256"] = sha(version / "processing.json")
        if variant == "positive":
            proof["required_source_hashes"] = {
                name: processing["original_source_hashes"][name]
                for name in ("original-trace.jsonl", "context.json", "receipt.json", "cameras.json")}
    if feedback:
        proof["feedback_sha256"] = sha(version / "feedback.json")
        if "classification" in feedback:
            proof["feedback_classification"] = feedback["classification"]
        if "error_type" in feedback:
            proof["feedback_error_type"] = feedback["error_type"]
    return proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", action="store_true")
    parser.add_argument("--case")
    args = parser.parse_args()
    manifest_path = WORK / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    SCRATCH.mkdir(parents=True, exist_ok=True)
    if args.bind:
        for entry in manifest["cases"]:
            case = entry["case_id"]
            command = ("PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved "
                       f"--manifest work/{ASSIGNMENT}/execution-manifest.json --case {case} "
                       '--attempt "$ATTEMPT" --output "$SAVED_OUTPUT" '
                       '--library "$LIBRARY" --validator "$VALIDATOR" '
                       '--owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
            entry["post_capture"] = {"recorded_only": True, "command": command,
                                      "feedback_command": command,
                                      "proof_scope": "Source-shaped diagnostic only; original Native and physical review pending"}
        write(manifest_path, manifest)
        print("bound", len(manifest["cases"]))
        return
    selected = [entry for entry in manifest["cases"]
                if args.case is None or entry["case_id"].endswith("__" + args.case)]
    if not selected:
        raise ValueError("No exact case selected")
    proof_path = WORK / "post-capture-proofs.json"
    current = json.loads(proof_path.read_text()) if proof_path.is_file() else {
        "format": "worker-recorded-only-post-capture-proofs", "assignment_id": ASSIGNMENT,
        "scope": "Source-shaped synthetic diagnostic only; no original Native or physical acceptance claim",
        "cases": []}
    by_id = {item["case_id"]: item for item in current["cases"]}
    for entry in selected:
        item = {"case_id": entry["case_id"], "variants": {}}
        for variant in ("positive", "missing-source", "missing-validator"):
            item["variants"][variant] = prove(entry, variant)
        by_id[entry["case_id"]] = item
        tag = entry["case_id"].rsplit("__", 1)[-1]
        entry["post_capture"].update({"test_exit_code": 0,
                                      "test_log": item["variants"]["positive"]["log"],
                                      "test_log_sha256": item["variants"]["positive"]["log_sha256"]})
        current["cases"] = [by_id[k] for k in sorted(by_id)]
        write(proof_path, current)
        write(manifest_path, manifest)
        print("proved", tag, flush=True)
    checksum = sha(proof_path)
    for entry in manifest["cases"]:
        if entry["case_id"] in by_id:
            entry["post_capture"]["feedback_proofs"] = {
                "receipt": proof_path.name, "sha256": checksum,
                "variants": ["missing-source", "missing-validator"]}
    write(manifest_path, manifest)


if __name__ == "__main__":
    main()
