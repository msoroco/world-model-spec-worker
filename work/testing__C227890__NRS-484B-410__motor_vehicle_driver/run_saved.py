"""Prove selected recorded-only analysis and missing-source feedback per case."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _capture(original, target, case_id, construction_sha, manifest_sha):
    if target.exists():
        raise ValueError("refusing to replace saved diagnostic input")
    shutil.copytree(original, target)
    selection = target / "candidate-selection.json"
    if selection.is_file():
        value = json.loads(selection.read_text())
        if value.get("case_id") != case_id or value.get("construction_sha256") != construction_sha:
            raise ValueError("diagnostic candidate identity differs")
        value["manifest_sha256"] = manifest_sha
        selection.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _run(case_id, attempt, output, log):
    command = [sys.executable, str(REPO / "runtime.py"), "process-saved",
               "--manifest", str(MANIFEST), "--case", case_id,
               "--attempt", str(attempt), "--output", str(output),
               "--library", str(REPO / "runtime/library"),
               "--validator", str(VALIDATOR)]
    process = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                             timeout=600, env=os.environ.copy())
    log.write_text("\n".join(line.rstrip() for line in
                             (process.stdout + process.stderr).splitlines()).rstrip() + "\n")
    if process.returncode:
        raise ValueError("recorded-only processing failed: " + log.read_text()[-1200:])
    return command, json.loads(process.stdout)


def run():
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    compat = Path(os.environ["C227890_COMPATIBILITY_ROOT"]).resolve()
    if ".runtime-work" not in scratch.parts or ".runtime-work" not in compat.parts:
        raise ValueError("saved proof scratch and compatibility root must be under .runtime-work")
    scratch.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    manifest_sha = _sha(MANIFEST)
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        variant = case_id.removeprefix(manifest["assignment_id"] + "__")
        original = compat / ("compat-" + variant + "-primary")
        if not original.is_dir():
            raise ValueError("compatibility original missing: " + variant)
        attempt = scratch / ("recorded-" + variant)
        _capture(original, attempt, case_id, entry["construction_sha256"], manifest_sha)
        positive_log = ROOT / ("cpu-saved-" + variant + ".log")
        command, receipt = _run(case_id, attempt, scratch / ("saved-" + variant), positive_log)
        if (receipt.get("passed") is not True or receipt.get("recorded_only") is not True or
                receipt.get("missing_evidence") is not False or
                receipt.get("analysis_revision", {}).get("construction_sha256") != entry["construction_sha256"]):
            raise ValueError("recorded-only positive result differs: " + variant)
        missing = scratch / ("recorded-" + variant + "-missing")
        _capture(original, missing, case_id, entry["construction_sha256"], manifest_sha)
        (missing / "original-attempt/activity.jsonl").unlink()
        negative_log = ROOT / ("cpu-saved-" + variant + "-missing.log")
        _, rejected = _run(case_id, missing, scratch / ("saved-" + variant + "-missing"), negative_log)
        if (rejected.get("passed") is not True or rejected.get("recorded_only") is not True or
                rejected.get("missing_evidence") is not True or
                not rejected.get("analysis_directory")):
            raise ValueError("recorded-only missing-source feedback differs: " + variant)
        entry["post_capture"] = {
            "command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + ROOT.name +
                       "/execution-manifest.json --case " + case_id +
                       " --attempt \"$ATTEMPT\" --output \"$PROCESSED\" --library runtime/library"
                       " --validator \"$LEAN_VALIDATOR\" --owner-release-receipt \"$OWNER_RELEASE_RECEIPT\"",
            "feedback_command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + ROOT.name +
                       "/execution-manifest.json --case " + case_id +
                       " --attempt \"$ATTEMPT\" --output \"$PROCESSED\" --library runtime/library"
                       " --validator \"$LEAN_VALIDATOR\" --owner-release-receipt \"$OWNER_RELEASE_RECEIPT\"",
            "recorded_only": True,
            "scope": "synthetic recorded-only replay; original parked departure and legal review pending",
            "test_exit_code": 0, "test_log": positive_log.name,
            "test_log_sha256": _sha(positive_log),
            "negative_test_log": negative_log.name,
            "negative_test_log_sha256": _sha(negative_log),
        }
        print(variant, "saved positive and missing-source feedback passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    run()
