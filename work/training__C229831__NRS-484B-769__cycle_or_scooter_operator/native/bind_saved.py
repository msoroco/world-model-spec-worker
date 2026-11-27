"""Run exact diagnostic saved-only processing and bind immutable receipts."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent
SCRATCH = REPO / ".runtime-work/c229831-temp"
MANIFEST = FOLDER / "execution-manifest.json"
VALIDATOR = SCRATCH / "validator/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args, log):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               TMPDIR=str(SCRATCH), SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH))
    completed = subprocess.run([sys.executable, str(REPO / "runtime.py"), *args],
                               cwd=REPO, env=env, capture_output=True, text=True)
    log.write_text((completed.stdout + completed.stderr).strip() + "\n")
    if completed.returncode:
        raise ValueError("Saved-only command failed: " + log.read_text()[-1000:])
    return completed


def prepare(label, case, recipe):
    source = SCRATCH / f"saved-attempt-{label}-v3"
    selected = SCRATCH / f"saved-selected-{label}-v3"
    if source.exists() or selected.exists():
        raise ValueError("Retain prior scratch; choose a new saved-proof version")
    run("fixture", "--recipe", str(REPO / recipe), "--output", str(source),
        log=SCRATCH / f"saved-fixture-{label}-v3.log")
    run("materialize", "--manifest", str(MANIFEST), "--case", case,
        "--output", str(selected), log=SCRATCH / f"saved-materialize-{label}-v3.log")
    for path in source.iterdir():
        target = selected / path.name
        if target.exists():
            raise ValueError("Fixture overwrites selected construction")
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)
    seal_path = selected / "capture-seal.json"
    seal = json.loads(seal_path.read_text())
    seal.update({"provenance_kind": "native", "diagnostic_fixture": True,
                 "events": ["capture_finished", "encoders_closed", "restoration_verified"],
                 "native_revision": {"construction_sha256": sha(selected / "construction.json"),
                                     "runner_sha256": sha(selected / "runner.py")}})
    seal_path.write_text(json.dumps(seal, indent=2) + "\n")
    (selected / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
    (selected / "native-exit.json").write_text(json.dumps({
        "event": "native_exit", "capture_seal_sha256": sha(seal_path),
        "native_revision": seal["native_revision"]}, indent=2) + "\n")
    return selected


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        label = case.rsplit("_", 1)[-1]
        if label == "a":
            selected = SCRATCH / "saved-selected-a"
            derived = SCRATCH / "saved-derived-a-v2"
            if not (derived / "v0001/processing.json").is_file():
                raise ValueError("Existing probe a saved receipt missing")
        else:
            selected = prepare(label, case, entry["fixture_recipe"])
            derived = SCRATCH / f"saved-derived-{label}-v3"
            run("process-saved", "--manifest", str(MANIFEST), "--case", case,
                "--attempt", str(selected), "--output", str(derived),
                "--library", str(REPO / "runtime/library"),
                "--validator", str(VALIDATOR),
                log=SCRATCH / f"saved-process-{label}-v3.log")
        source_receipt = derived / "v0001/processing.json"
        receipt = json.loads(source_receipt.read_text())
        if (not receipt["passed"] or receipt["missing_evidence"] or
                not receipt["recorded_only"] or not receipt["originals_preserved"] or
                receipt["timestamp_joins"]["frames"] != 600):
            raise ValueError("Saved-only result incomplete")
        target = FOLDER / "proofs" / label / "primary"
        target.mkdir(parents=True, exist_ok=True)
        copied = target / "processing.json"
        shutil.copyfile(source_receipt, copied)
        log = target / "saved-processing.log"
        log.write_text(json.dumps({"command": "runtime.py process-saved",
                                   "case_id": case, "exit_code": 0,
                                   "passed": True, "missing_evidence": False,
                                   "originals_preserved": True,
                                   "diagnostic_fixture": True}) + "\n")
        entry["saved_processing"] = {"receipt": copied.relative_to(FOLDER).as_posix(),
                                     "sha256": sha(copied)}
        entry["post_capture"] = {
            "recorded_only": True,
            "command": f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{FOLDER.name}/execution-manifest.json --case {case} --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library --validator "$VALIDATOR"',
            "feedback_command": 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            "test_exit_code": 0, "test_log": log.relative_to(FOLDER).as_posix(),
            "test_log_sha256": sha(log), "proof": copied.relative_to(FOLDER).as_posix()}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"saved_only_diagnostic_receipts": 3,
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
