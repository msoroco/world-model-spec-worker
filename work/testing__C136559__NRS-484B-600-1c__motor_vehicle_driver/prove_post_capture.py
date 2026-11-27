"""Exercise recorded-only saved processing and missing-source feedback for every case."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c136559-600-1c/post-capture"
MANIFEST = ROOT / "execution-manifest.json"
PYTHON = REPO / ".venv-cpu/bin/python"
VALIDATOR = REPO / ".runtime-work/c150099-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case: str, attempt: Path, output: Path, log: Path, env: dict[str, str],
        validator: Path = VALIDATOR) -> subprocess.CompletedProcess[str]:
    command = [str(PYTHON), "runtime.py", "process-saved", "--manifest", str(MANIFEST),
               "--case", case, "--attempt", str(attempt), "--output", str(output),
               "--library", str(REPO / "runtime/library"), "--validator", str(validator)]
    completed = subprocess.run(command, cwd=REPO, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(completed.stdout.rstrip() + "\n")
    return completed


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / "tmp").mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH / "tmp"),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "output"))
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(ROOT.name + "__")
        source = REPO / entry["saved_diagnostic"]["source"]
        attempt = SCRATCH / (suffix + "-attempt")
        positive = SCRATCH / (suffix + "-positive")
        negative = SCRATCH / (suffix + "-missing-source")
        for path in (attempt, positive, negative):
            if path.exists():
                shutil.rmtree(path)
        materialize = [str(PYTHON), "runtime.py", "materialize", "--manifest", str(MANIFEST),
                       "--case", case, "--output", str(attempt)]
        subprocess.run(materialize, cwd=REPO, env=env, check=True, capture_output=True, text=True)
        for path in source.iterdir():
            target = attempt / path.name
            if target.exists():
                raise ValueError("diagnostic source shadows construction: " + str(target))
            if path.is_dir():
                shutil.copytree(path, target)
            else:
                shutil.copy2(path, target)
        # The primary is selected by default; avoid a receipt tied to a prior
        # manifest revision while preserving the exact selected construction.
        (attempt / "candidate-selection.json").unlink(missing_ok=True)
        positive_log = ROOT / ("cpu-post-capture-" + suffix + ".log")
        completed = run(case, attempt, positive, positive_log, env)
        if completed.returncode:
            raise ValueError("saved-only positive failed: " + case + "\n" + completed.stdout[-1600:])
        positive_receipt = json.loads((positive / "v0001/processing.json").read_text())
        if not positive_receipt["passed"] or not positive_receipt["recorded_only"] or positive_receipt["missing_evidence"]:
            raise ValueError("positive saved-processing receipt incomplete: " + case)
        if not positive_receipt["originals_preserved"] or not positive_receipt["timestamp_joins"]["passed"]:
            raise ValueError("positive source or frame join unverified: " + case)
        missing_attempt = SCRATCH / (suffix + "-missing-attempt")
        if missing_attempt.exists():
            shutil.rmtree(missing_attempt)
        shutil.copytree(attempt, missing_attempt)
        (missing_attempt / "original-attempt/posted-speed-source.json").unlink()
        negative_log = ROOT / ("cpu-post-feedback-" + suffix + ".log")
        completed = run(case, missing_attempt, negative, negative_log, env)
        feedback = json.loads((negative / "v0001/feedback.json").read_text())
        if not feedback.get("recorded_only") or feedback.get("native_replay_requested") is not False:
            raise ValueError("missing-source feedback requested replay: " + case)
        if "Missing required source: original-attempt/posted-speed-source.json" not in feedback.get("error", ""):
            raise ValueError("missing-source feedback omitted exact source: " + case)
        if completed.returncode == 0:
            receipt = json.loads((negative / "v0001/processing.json").read_text())
            if not receipt["missing_evidence"] or not receipt["recorded_only"]:
                raise ValueError("missing source silently accepted: " + case)
        missing_validator = SCRATCH / (suffix + "-missing-validator")
        if missing_validator.exists():
            shutil.rmtree(missing_validator)
        validator_log = ROOT / ("cpu-post-validator-" + suffix + ".log")
        validator_result = run(case, attempt, missing_validator, validator_log, env,
                               SCRATCH / "absent-validator")
        validator_feedback_path = missing_validator / "v0001/feedback.json"
        validator_feedback = json.loads(validator_feedback_path.read_text())
        if validator_result.returncode == 0 or validator_feedback.get("recorded_only") is not True:
            raise ValueError("missing validator silently accepted: " + case)
        if validator_feedback.get("native_replay_requested") is not False:
            raise ValueError("missing validator requested Native replay: " + case)
        feedback_log = ROOT / ("cpu-feedback-command-" + suffix + ".log")
        feedback_result = subprocess.run([str(PYTHON), str(ROOT / "post_capture_feedback.py"),
                                          "--output", str(negative)], cwd=REPO, env=env,
                                         text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        feedback_log.write_text(feedback_result.stdout.rstrip() + "\n")
        if feedback_result.returncode or not json.loads(feedback_result.stdout)["recorded_only"]:
            raise ValueError("feedback command failed: " + case)
        entry["post_capture"] = {
            "recorded_only": True,
            "command": f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved --manifest work/{ROOT.name}/execution-manifest.json --case {case} --attempt "$ATTEMPT" --output "$OUTPUT" --library runtime/library --validator "$VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
            "feedback_command": 'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' + ROOT.name + '/post_capture_feedback.py --output "$OUTPUT"',
            "test_exit_code": 0, "test_log": positive_log.name,
            "test_log_sha256": sha(positive_log),
            "missing_source_test_exit_code": completed.returncode,
            "missing_source_test_log": negative_log.name,
            "missing_source_test_log_sha256": sha(negative_log),
            "missing_source_feedback": str((negative / "v0001/feedback.json").relative_to(REPO)),
            "missing_source_feedback_sha256": sha(negative / "v0001/feedback.json"),
            "missing_source": "original-attempt/posted-speed-source.json",
            "missing_validator_test_exit_code": validator_result.returncode,
            "missing_validator_test_log": validator_log.name,
            "missing_validator_test_log_sha256": sha(validator_log),
            "missing_validator_feedback": str(validator_feedback_path.relative_to(REPO)),
            "missing_validator_feedback_sha256": sha(validator_feedback_path),
            "feedback_test_exit_code": 0,
            "feedback_test_log": feedback_log.name,
            "feedback_test_log_sha256": sha(feedback_log),
            "source_shape": "source-hashed diagnostic posted-speed packet, trace, frame map and four camera sources",
        }
        print(suffix + " positive and missing-source feedback passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
