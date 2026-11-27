"""Exercise recorded-only processing and feedback with source-shaped CPU fixtures."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OWN = Path(__file__).resolve().parent
SCRATCH = ROOT / ".runtime-work" / "c412262-postcapture-nov27"
MANIFEST = OWN / "execution-manifest.json"
VALIDATOR = ROOT / ".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def invoke(case_id, attempt, output, validator):
    command = [sys.executable, str(ROOT / "runtime.py"), "process-saved",
               "--manifest", str(MANIFEST), "--case", case_id,
               "--attempt", str(attempt), "--output", str(output),
               "--library", str(ROOT / "runtime/library"),
               "--validator", str(validator)]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH)
    env["TMPDIR"] = str(SCRATCH)
    completed = subprocess.run(command, cwd=ROOT, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    version = output / "v0001"
    return completed, version


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        short = case.rsplit("__", 1)[1]
        source = Path(entry["compatibility"]["command"].split("--output ", 1)[1].split(" --library", 1)[0])
        if not source.is_dir():
            raise RuntimeError("Missing compatibility source: " + str(source))
        case_root = SCRATCH / short
        if case_root.exists():
            shutil.rmtree(case_root)
        case_root.mkdir()
        attempt = case_root / "attempt"
        shutil.copytree(source, attempt)
        (attempt / "candidate-selection.json").unlink(missing_ok=True)
        before = {str(p.relative_to(attempt)): sha(p) for p in attempt.rglob("*") if p.is_file()}
        positive, version = invoke(case, attempt, case_root / "positive", VALIDATOR)
        if positive.returncode:
            raise RuntimeError(short + " positive saved processing failed: " + positive.stdout[-2000:])
        receipt = json.loads((version / "processing.json").read_text())
        if not (receipt["passed"] and receipt["recorded_only"] and
                receipt["originals_preserved"] and receipt["timestamp_joins"]["passed"] and
                receipt["final_video_checks"]["passed"] and
                not receipt["missing_evidence"] and
                not receipt["physical_acceptance_claimed"] and
                not receipt["legal_acceptance_claimed"]):
            raise RuntimeError(short + " positive receipt did not prove saved path")
        after = {str(p.relative_to(attempt)): sha(p) for p in attempt.rglob("*") if p.is_file()}
        if before != after:
            raise RuntimeError(short + " saved processing mutated acquisition")
        missing_attempt = case_root / "missing-context"
        shutil.copytree(attempt, missing_attempt)
        (missing_attempt / "context.json").unlink()
        missing, missing_version = invoke(case, missing_attempt, case_root / "missing", VALIDATOR)
        missing_receipt = json.loads((missing_version / "processing.json").read_text())
        missing_feedback = json.loads((missing_version / "feedback.json").read_text())
        if (missing.returncode or not missing_receipt["missing_evidence"] or
                missing_feedback.get("classification") != "incomplete_or_unavailable_law_evidence" or
                not missing_feedback["recorded_only"] or missing_feedback["native_replay_requested"] or
                "Missing required source: context.json" not in missing_feedback["error"]):
            raise RuntimeError(short + " missing-source feedback mismatch: " + missing.stdout[-2000:])
        invalid, invalid_version = invoke(case, attempt, case_root / "invalid-validator",
                                          case_root / "unavailable-validator")
        invalid_feedback = json.loads((invalid_version / "feedback.json").read_text())
        if (invalid.returncode == 0 or invalid_feedback.get("recorded_only") is not True or
                invalid_feedback.get("native_replay_requested") is not False or
                "validator" not in invalid_feedback.get("error", "").lower()):
            raise RuntimeError(short + " unavailable-validator feedback mismatch: " + invalid.stdout[-2000:])
        proof = {
            "format": "worker-post-capture-cpu-proof", "case_id": case,
            "source_kind": "synthetic_diagnostic_fixture", "recorded_only": True,
            "positive": {"exit_code": positive.returncode, "processing_sha256": sha(version / "processing.json"),
                         "originals_preserved": True, "source_video_frames": receipt["final_video_checks"]["frames"]},
            "missing_source": {"exit_code": missing.returncode,
                               "feedback_sha256": sha(missing_version / "feedback.json"),
                               "classification": missing_feedback["classification"]},
            "missing_validator": {"exit_code": invalid.returncode,
                                  "feedback_sha256": sha(invalid_version / "feedback.json"),
                                  "error_type": invalid_feedback["error_type"]},
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False,
        }
        (OWN / f"cpu-process-saved-{short}-proof.json").write_text(
            json.dumps(proof, indent=2, sort_keys=True) + "\n")
        log = OWN / f"cpu-process-saved-{short}.log"
        log.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
        entry["post_capture"]["test_log_sha256"] = sha(log)
        print(short + ": saved positive, missing source, unavailable validator passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
