"""Bind all exact cases to current recorded-only processing and feedback."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
SCRATCH = REPO / ".runtime-work/c202480-owner/post-capture"
PYTHON = REPO / ".venv-cpu/bin/python"
VALIDATOR = REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case, attempt, output, validator, log, env):
    command = [str(PYTHON), "runtime.py", "process-saved", "--manifest", str(MANIFEST),
               "--case", case, "--attempt", str(attempt), "--output", str(output),
               "--library", str(REPO / "runtime/library"), "--validator", str(validator)]
    completed = subprocess.run(command, cwd=REPO, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
    log.write_text(completed.stdout.rstrip("\n") + "\n")
    return completed


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    temp = SCRATCH / "tmp"
    temp.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(temp),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "output"))
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(HERE.name + "__")
        source = REPO / ".runtime-work/c202480-owner/saved" / suffix / "positive-attempt"
        if not source.is_dir():
            raise ValueError("Missing source-shaped saved fixture: " + str(source))
        attempt = SCRATCH / (suffix + "-attempt")
        positive = SCRATCH / (suffix + "-positive")
        missing_source_attempt = SCRATCH / (suffix + "-missing-source-attempt")
        missing_source = SCRATCH / (suffix + "-missing-source")
        missing_validator = SCRATCH / (suffix + "-missing-validator")
        for path in (attempt, positive, missing_source_attempt, missing_source, missing_validator):
            if path.exists():
                shutil.rmtree(path)
        shutil.copytree(source, attempt)
        (attempt / "candidate-selection.json").unlink(missing_ok=True)
        positive_log = HERE / ("post-capture-" + suffix + "-positive.log")
        completed = run(case, attempt, positive, VALIDATOR, positive_log, env)
        if completed.returncode:
            raise ValueError("Positive saved processing failed: " + case + "\n" + completed.stdout[-1200:])
        receipt = json.loads((positive / "v0001/processing.json").read_text())
        if not (receipt["recorded_only"] and receipt["originals_preserved"] and
                receipt["timestamp_joins"]["passed"] and not receipt["missing_evidence"]):
            raise ValueError("Incomplete positive saved receipt: " + case)
        shutil.copytree(attempt, missing_source_attempt)
        (missing_source_attempt / "native-stop-device.json").unlink()
        source_log = HERE / ("post-capture-" + suffix + "-missing-source.log")
        source_result = run(case, missing_source_attempt, missing_source, VALIDATOR, source_log, env)
        source_feedback = missing_source / "v0001/feedback.json"
        source_record = json.loads(source_feedback.read_text())
        if (source_result.returncode == 0 or not source_record.get("recorded_only") or
                source_record.get("native_replay_requested") is not False or
                "missing source file: native_stop_device" not in source_record.get("error", "")):
            raise ValueError("Missing source feedback failed: " + case)
        validator_log = HERE / ("post-capture-" + suffix + "-missing-validator.log")
        validator_result = run(case, attempt, missing_validator, SCRATCH / "absent-validator", validator_log, env)
        validator_feedback = missing_validator / "v0001/feedback.json"
        validator_record = json.loads(validator_feedback.read_text())
        if (validator_result.returncode == 0 or not validator_record.get("recorded_only") or
                validator_record.get("native_replay_requested") is not False):
            raise ValueError("Missing validator feedback failed: " + case)
        feedback_log = HERE / ("post-capture-" + suffix + "-feedback.log")
        feedback_result = subprocess.run([str(PYTHON), str(HERE / "post_capture_feedback.py"),
                                          "--output", str(missing_source)], cwd=REPO, env=env,
                                         text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        feedback_log.write_text(feedback_result.stdout.rstrip("\n") + "\n")
        if feedback_result.returncode or not json.loads(feedback_result.stdout)["recorded_only"]:
            raise ValueError("Feedback command failed: " + case)
        entry["post_capture"] = {
            "recorded_only": True,
            "command": f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {case} --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library "$LIBRARY" --validator "$VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
            "feedback_command": f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{HERE.name}/post_capture_feedback.py --output "$SAVED_OUTPUT"',
            "test_exit_code": 0, "test_log": positive_log.name, "test_log_sha256": sha(positive_log),
            "missing_source_test_exit_code": source_result.returncode,
            "missing_source_test_log": source_log.name, "missing_source_test_log_sha256": sha(source_log),
            "missing_source_feedback_sha256": sha(source_feedback),
            "missing_validator_test_exit_code": validator_result.returncode,
            "missing_validator_test_log": validator_log.name, "missing_validator_test_log_sha256": sha(validator_log),
            "missing_validator_feedback_sha256": sha(validator_feedback),
            "feedback_test_exit_code": 0, "feedback_test_log": feedback_log.name,
            "feedback_test_log_sha256": sha(feedback_log),
            "source_shape": "source-hashed rail stop, conflict history, trace, frame map, and four camera videos",
        }
        print(suffix + ": positive, missing source, missing validator, feedback passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
