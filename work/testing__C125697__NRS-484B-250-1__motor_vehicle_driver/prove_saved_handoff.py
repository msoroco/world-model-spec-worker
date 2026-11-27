"""Prove the exact selected saved-only and failure-feedback commands on CPU fixtures."""
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


def invoke(args: list[str], output_root: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(output_root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(args, cwd=REPO, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=600)


def command_tokens(spec: str, case_id: str, attempt: Path, output: Path,
                   owner_receipt: Path) -> list[str]:
    tokens = shlex.split(spec)
    if tokens[:4] != ["PYTHONDONTWRITEBYTECODE=1", ".venv-cpu/bin/python",
                      "runtime.py", "process-saved"]:
        raise ValueError("saved-only command does not select runtime.py process-saved")
    if tokens[tokens.index("--case") + 1] != case_id:
        raise ValueError("saved-only command selects another exact case")
    for flag, value in (("--attempt", attempt), ("--output", output),
                        ("--library", REPO / "runtime/library"),
                        ("--validator", VALIDATOR),
                        ("--owner-release-receipt", owner_receipt)):
        tokens[tokens.index(flag) + 1] = str(value)
    return tokens[1:]


def owner_fixture_receipt(attempt: Path) -> Path:
    """Explicit synthetic owner-release protocol fixture, never a physical claim."""
    receipt = attempt / "owner-release.json"
    receipt.write_text(json.dumps({"event": "owner_released", "operator_attested": True,
        "native_construction_sha256": sha(attempt / "construction.json"),
        "native_exit_sha256": None, "no_resource_operation_performed": True,
        "diagnostic_fixture": True}, indent=2) + "\n")
    return receipt


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
        case_root = scratch / suffix
        case_root.mkdir()
        recipe = REPO / entry["fixture_recipe"]
        fixture, attempt = case_root / "fixture", case_root / "attempt"
        materialized = invoke([".venv-cpu/bin/python", "runtime.py", "fixture",
            "--recipe", str(recipe), "--output", str(fixture)], case_root / "runtime-fixture")
        if materialized.returncode:
            raise ValueError(suffix + " fixture: " + materialized.stdout[-1200:])
        selected = invoke([".venv-cpu/bin/python", "runtime.py", "materialize",
            "--manifest", str(manifest), "--case", case_id, "--output", str(attempt)],
            case_root / "runtime-materialize")
        if selected.returncode:
            raise ValueError(suffix + " materialize: " + selected.stdout[-1200:])
        if sha(attempt / "construction.json") != entry["construction_sha256"]:
            raise ValueError("selected construction changed: " + suffix)
        # Primary diagnostic fixture has no Native selection receipt. This keeps
        # the test reproducible after only the manifest's proof metadata changes.
        (attempt / "candidate-selection.json").unlink()
        for source in fixture.iterdir():
            target = attempt / source.name
            if target.exists():
                raise ValueError("fixture shadows selected construction: " + source.name)
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        owner = owner_fixture_receipt(attempt)
        positive = case_root / "saved-positive"
        positive_run = invoke(command_tokens(entry["post_capture"]["command"], case_id,
                                             attempt, positive, owner), case_root / "runtime-positive")
        processing = positive / "v0001/processing.json"
        if positive_run.returncode or not processing.is_file():
            raise ValueError(suffix + " saved positive failed: " + positive_run.stdout[-1200:])
        receipt = json.loads(processing.read_text())
        if (receipt.get("passed") is not True or receipt.get("recorded_only") is not True or
                receipt.get("case_id") != case_id or
                receipt.get("physical_acceptance_claimed") is not False or
                receipt.get("originals_preserved") is not True):
            raise ValueError("incomplete saved-only processing receipt: " + suffix)
        negative = case_root / "attempt-missing-source"
        shutil.copytree(attempt, negative)
        (negative / "native_trace.json").unlink()
        negative_owner = negative / "owner-release.json"
        negative_output = case_root / "saved-negative"
        negative_run = invoke(command_tokens(entry["post_capture"]["feedback_command"],
                            case_id, negative, negative_output, negative_owner),
                            case_root / "runtime-negative")
        feedback = negative_output / "v0001/feedback.json"
        if not feedback.is_file():
            raise ValueError(suffix + " missing-source feedback absent: " + negative_run.stdout[-1200:])
        failure = json.loads(feedback.read_text())
        if (failure.get("recorded_only") is not True or
                failure.get("native_replay_requested") is not False or
                not failure.get("error")):
            raise ValueError("nonactionable saved-only feedback: " + suffix)
        rows.append({"case_id": case_id, "construction_sha256": entry["construction_sha256"],
            "processing_sha256": sha(processing), "feedback_sha256": sha(feedback),
            "positive_exit_code": positive_run.returncode,
            "negative_exit_code": negative_run.returncode,
            "recorded_only": True, "native_replay_requested": False})
    proof = {"format": "c125697-selected-saved-handoff-proof", "cases": rows,
        "diagnostic_fixture": True, "physical_acceptance_claimed": False,
        "negative_removed": "native_trace.json",
        "scope": "CPU selected-construction saved analysis and missing-original feedback only"}
    (ROOT / "saved-handoff-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"cases": len(rows), "positive_saved_processing": True,
                      "negative_feedback": True, "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
