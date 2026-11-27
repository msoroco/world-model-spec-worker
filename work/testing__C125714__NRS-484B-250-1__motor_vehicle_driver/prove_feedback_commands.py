"""Exercise every exact saved-only feedback command on a missing-source fixture."""
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


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", required=True)
    args = parser.parse_args()
    scratch = Path(args.scratch).resolve()
    if not scratch.is_relative_to((REPO / ".runtime-work").resolve()):
        raise ValueError("scratch must be under .runtime-work")
    if scratch.exists():
        raise ValueError("choose a fresh scratch directory")
    scratch.mkdir(parents=True)
    manifest = ROOT / "execution-manifest.json"
    entries = json.loads(manifest.read_text())["cases"]
    rows = []
    for entry in entries:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        original = REPO / ".runtime-work" / "c125714-nov26" / f"saved-final-{suffix}-input"
        attempt = scratch / suffix / "attempt"
        output = scratch / suffix / "saved"
        shutil.copytree(original, attempt)
        missing = attempt / "ego-body-history.jsonl"
        if not missing.is_file():
            raise ValueError("fixture source missing before negative probe: " + suffix)
        missing.unlink()
        owner_receipt = attempt / "owner-release.json"
        owner_receipt.write_text(json.dumps({
            "event": "owner_released", "operator_attested": True,
            "native_construction_sha256": digest(attempt / "construction.json"),
            "native_exit_sha256": None, "no_resource_operation_performed": True,
            "diagnostic_fixture": True,
        }, indent=2) + "\n")
        command = shlex.split(entry["post_capture"]["feedback_command"])
        if command[0:4] != ["PYTHONDONTWRITEBYTECODE=1", ".venv-cpu/bin/python",
                            "runtime.py", "process-saved"]:
            raise ValueError("feedback command does not use saved-only runtime path")
        if command[command.index("--case") + 1] != case_id:
            raise ValueError("feedback command targets another case")
        for flag, value in (("--attempt", str(attempt)), ("--output", str(output)),
                            ("--library", str(REPO / "runtime/library")),
                            ("--validator", str(REPO / ".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck")),
                            ("--owner-release-receipt", str(owner_receipt))):
            command[command.index(flag) + 1] = value
        env = dict(os.environ)
        env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(scratch / suffix / "runtime-output")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(command[1:], cwd=REPO, env=env, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   timeout=300)
        versions = sorted(output.glob("v*/feedback.json"))
        if not versions:
            raise ValueError("saved-only command produced no failure feedback: " + suffix + "\n" + completed.stdout[-1000:])
        feedback = json.loads(versions[-1].read_text())
        if (feedback.get("recorded_only") is not True or
                feedback.get("native_replay_requested") is not False or
                not feedback.get("error")):
            raise ValueError("feedback does not identify saved-only failure: " + suffix)
        rows.append({"case_id": case_id, "feedback_sha256": digest(versions[-1]),
                     "classification": feedback.get("classification", feedback.get("error_type")),
                     "recorded_only": True, "native_replay_requested": False,
                     "process_exit_code": completed.returncode})
    proof = {"format": "c125714-exact-saved-feedback-proof", "manifest_sha256": digest(manifest),
             "cases": rows, "synthetic_missing_source": "ego-body-history.jsonl",
             "scope": "CPU diagnostic feedback path only; no physical or legal acceptance"}
    (ROOT / "feedback-commands-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"cases": len(rows), "recorded_only_feedback": True,
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
