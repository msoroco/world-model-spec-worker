"""Exercise every selected case through current recorded-only processing."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
MANIFEST = PACKAGE / "execution-manifest.json"
SCRATCH = REPO / ".runtime-work/c111125-postcapture"
LIBRARY = REPO / "runtime/library"
VALIDATOR = REPO / ".runtime-work/c111125-owner/validator/.lake/build/bin/adapterCheck"


def invoke(*args):
    return subprocess.run(
        [sys.executable, str(REPO / "runtime.py"), *map(str, args)],
        cwd=REPO,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
             "SCENARIO_PIPELINE_OUTPUT_ROOT": str(SCRATCH),
             "TMPDIR": str(SCRATCH / "tmp")},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / "tmp").mkdir(exist_ok=True)
    cases = json.loads(MANIFEST.read_text())["cases"]
    for entry in cases:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        attempt = SCRATCH / (suffix + "-attempt")
        saved = SCRATCH / (suffix + "-saved")
        negative = SCRATCH / (suffix + "-missing-source")
        feedback = SCRATCH / (suffix + "-feedback")
        validator_feedback = SCRATCH / (suffix + "-validator-feedback")
        for path in (attempt, saved, negative, feedback, validator_feedback):
            if path.exists():
                shutil.rmtree(path)
        process_args = ("process-saved", "--manifest", MANIFEST,
                        "--case", case, "--attempt", attempt,
                        "--output", saved, "--library", LIBRARY,
                        "--validator", VALIDATOR)
        result = invoke("compatibility", "--manifest", MANIFEST,
                        "--case", case, "--output", attempt,
                        "--library", LIBRARY, "--validator", VALIDATOR)
        if result.returncode:
            raise AssertionError(f"{suffix}: compatibility failed: {result.stdout[-1600:]}")
        # Primary diagnostic fixture can omit the optional selection receipt.
        # This avoids a manifest/log-hash cycle when this proof is bound below.
        (attempt / "candidate-selection.json").unlink()
        result = invoke(*process_args)
        if result.returncode:
            raise AssertionError(f"{suffix}: saved processing failed: {result.stdout[-1600:]}")
        receipt = json.loads((saved / "v0001/processing.json").read_text())
        assert receipt["case_id"] == case and receipt["passed"] is True
        assert receipt["recorded_only"] is True and receipt["originals_preserved"] is True
        assert receipt["missing_evidence"] is False
        assert receipt["timestamp_joins"]["passed"] is True
        assert receipt["final_video_checks"]["passed"] is True
        assert receipt["physical_acceptance_claimed"] is False
        shutil.copytree(attempt, negative, ignore=shutil.ignore_patterns("converted", "traffic_spec", "channels"))
        (negative / "head.json").unlink()
        result = invoke("process-saved", "--manifest", MANIFEST, "--case", case,
                        "--attempt", negative, "--output", feedback,
                        "--library", LIBRARY, "--validator", VALIDATOR)
        if result.returncode:
            raise AssertionError(f"{suffix}: missing-source feedback failed: {result.stdout[-1600:]}")
        finding = json.loads((feedback / "v0001/feedback.json").read_text())
        incomplete = json.loads((feedback / "v0001/processing.json").read_text())
        if incomplete["missing_evidence"] is not True or finding.get("classification") != "incomplete_or_unavailable_law_evidence":
            raise AssertionError(f"{suffix}: missing source was not classified incomplete")
        if not finding.get("recorded_only") or finding.get("native_replay_requested"):
            raise AssertionError(f"{suffix}: failure feedback requests Native replay")
        if "head.json" not in finding["error"]:
            raise AssertionError(f"{suffix}: missing source not identified: {finding}")
        result = invoke("process-saved", "--manifest", MANIFEST, "--case", case,
                        "--attempt", attempt, "--output", validator_feedback,
                        "--library", LIBRARY, "--validator", SCRATCH / "missing-validator")
        if result.returncode == 0:
            raise AssertionError(f"{suffix}: absent validator unexpectedly passed")
        finding = json.loads((validator_feedback / "v0001/feedback.json").read_text())
        if not finding.get("recorded_only") or finding.get("native_replay_requested"):
            raise AssertionError(f"{suffix}: validator feedback requests Native replay")
        if "validator" not in finding["error"].lower():
            raise AssertionError(f"{suffix}: validator failure not identified: {finding}")
        print(f"{case}: positive, missing head.json, and missing validator feedback passed", flush=True)


if __name__ == "__main__":
    main()
