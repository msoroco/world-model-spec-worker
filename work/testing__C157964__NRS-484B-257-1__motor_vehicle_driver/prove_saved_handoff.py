"""Exercise four exact selected saved-only commands and missing-source feedback."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
VALIDATOR = REPO / ".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(spec: str, case_id: str, attempt: Path, output: Path,
            owner_receipt: Path, runtime_output: Path) -> subprocess.CompletedProcess[str]:
    tokens = shlex.split(spec)
    if tokens[:4] != ["PYTHONDONTWRITEBYTECODE=1", ".venv-cpu/bin/python",
                      "runtime.py", "process-saved"]:
        raise ValueError("not an executable saved-only runtime command")
    if tokens[tokens.index("--case") + 1] != case_id:
        raise ValueError("feedback command selected another case")
    for flag, value in (("--attempt", attempt), ("--output", output),
                        ("--library", REPO / "runtime/library"),
                        ("--validator", VALIDATOR),
                        ("--owner-release-receipt", owner_receipt)):
        tokens[tokens.index(flag) + 1] = str(value)
    env = dict(os.environ)
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(runtime_output)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(tokens[1:], cwd=REPO, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=900)


def synthetic_attempt(source: Path, target: Path, expected_construction: str) -> Path:
    shutil.copytree(source, target, copy_function=os.link)
    if sha(target / "construction.json") != expected_construction:
        raise ValueError("source-shaped fixture has stale selected construction")
    (target / "candidate-selection.json").unlink()
    owner = target / "owner-release.json"
    owner.write_text(json.dumps({"event": "owner_released",
        "operator_attested": True,
        "native_construction_sha256": expected_construction,
        "native_exit_sha256": None,
        "no_resource_operation_performed": True,
        "diagnostic_fixture": True}, indent=2) + "\n")
    return owner


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", required=True)
    args = parser.parse_args()
    scratch = Path(args.scratch).resolve()
    if not scratch.is_relative_to((REPO / ".runtime-work").resolve()):
        raise ValueError("scratch belongs under .runtime-work")
    if scratch.exists():
        raise ValueError("choose a fresh scratch directory")
    scratch.mkdir(parents=True)
    manifest = ROOT / "execution-manifest.json"
    rows = []
    for entry in json.loads(manifest.read_text())["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        source = REPO / ".runtime-work" / ("c157964-selected-saved-source-v3-" + suffix)
        case_root = scratch / suffix
        case_root.mkdir()
        attempt = case_root / "positive-attempt"
        owner = synthetic_attempt(source, attempt, entry["construction_sha256"])
        positive = case_root / "saved-positive"
        good = execute(entry["post_capture"]["command"], case_id, attempt,
                       positive, owner, case_root / "runtime-positive")
        receipt_path = positive / "v0001/processing.json"
        if good.returncode or not receipt_path.is_file():
            raise ValueError(suffix + " saved-only processing failed: " + good.stdout[-1500:])
        receipt = json.loads(receipt_path.read_text())
        if (receipt.get("passed") is not True or receipt.get("recorded_only") is not True or
                receipt.get("case_id") != case_id or
                receipt.get("originals_preserved") is not True or
                receipt.get("physical_acceptance_claimed") is not False):
            raise ValueError("saved-only receipt lacks source preservation: " + suffix)
        negative_attempt = case_root / "missing-measurement-attempt"
        negative_owner = synthetic_attempt(source, negative_attempt,
                                           entry["construction_sha256"])
        missing = negative_attempt / "original-attempt/measurement.json"
        if not missing.is_file():
            raise ValueError("mandatory measurement source absent before negative probe")
        missing.unlink()
        negative = case_root / "saved-negative"
        bad = execute(entry["post_capture"]["feedback_command"], case_id,
                      negative_attempt, negative, negative_owner,
                      case_root / "runtime-negative")
        feedback_path = negative / "v0001/feedback.json"
        if not feedback_path.is_file():
            raise ValueError(suffix + " missing-measurement feedback absent: " + bad.stdout[-1500:])
        feedback = json.loads(feedback_path.read_text())
        if (feedback.get("recorded_only") is not True or
                feedback.get("native_replay_requested") is not False or
                not feedback.get("error")):
            raise ValueError("saved-only feedback not actionable: " + suffix)
        rows.append({"case_id": case_id,
                     "construction_sha256": entry["construction_sha256"],
                     "processing_sha256": sha(receipt_path),
                     "feedback_sha256": sha(feedback_path),
                     "positive_exit_code": good.returncode,
                     "negative_exit_code": bad.returncode,
                     "recorded_only": True, "native_replay_requested": False})
        print(json.dumps({"case": suffix, "saved_only": True, "feedback": True}))
    (ROOT / "saved-handoff-proof.json").write_text(json.dumps({
        "format": "c157964-exact-saved-handoff-proof", "cases": rows,
        "negative_removed": "original-attempt/measurement.json",
        "diagnostic_fixture": True, "physical_acceptance_claimed": False,
        "scope": "CPU source-shaped saved processing and missing-source feedback only",
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
