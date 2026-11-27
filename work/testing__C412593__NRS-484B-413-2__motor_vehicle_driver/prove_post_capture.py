"""Exercise recorded-only processing and failure feedback for one exact case."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
PRIVATE = REPO / ".runtime-work/c412593-postcapture"
VALIDATOR = REPO / ".runtime-work/c111125-owner/validator/.lake/build/bin/adapterCheck"


def run(args: list[str], env: dict[str, str], *, expected: int | None = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=REPO, env=env, text=True,
                            capture_output=True, timeout=300, check=False)
    if expected is not None and result.returncode != expected:
        raise RuntimeError(f"exit {result.returncode}, expected {expected}: {result.stderr[-2000:]}")
    return result


def processing(case: str, attempt: Path, output: Path, validator: Path,
               env: dict[str, str], *, expected: int | None = 0) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = run([sys.executable, str(REPO / "runtime.py"), "process-saved",
                  "--manifest", str(MANIFEST), "--case", case,
                  "--attempt", str(attempt), "--output", str(output),
                  "--library", str(REPO / "runtime/library"),
                  "--validator", str(validator)], env, expected=expected)
    version = output / "v0001"
    return result, json.loads((version / "processing.json").read_text()) if (version / "processing.json").is_file() else {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    case = args.case
    if case not in {item["case_id"] for item in json.loads(MANIFEST.read_text())["cases"]}:
        raise ValueError("Unknown exact case")
    if not VALIDATOR.is_file():
        raise FileNotFoundError(f"Pinned validator unavailable: {VALIDATOR}")
    PRIVATE.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(PRIVATE),
               TMPDIR=str(PRIVATE), PYTHONDONTWRITEBYTECODE="1")
    tag = case.rsplit("__", 1)[-1]
    home = PRIVATE / tag
    if home.exists():
        shutil.rmtree(home)
    home.mkdir()
    attempt = home / "attempt"
    run([sys.executable, str(REPO / "runtime.py"), "compatibility",
         "--manifest", str(MANIFEST), "--case", case,
         "--output", str(attempt), "--library", str(REPO / "runtime/library"),
         "--validator", str(VALIDATOR)], env)
    _, positive = processing(case, attempt, home / "positive", VALIDATOR, env)
    assert positive["recorded_only"] is True
    assert positive["passed"] is True and positive["missing_evidence"] is False
    assert positive["originals_preserved"] is True
    assert positive["final_video_checks"]["passed"] is True
    assert positive["physical_acceptance_claimed"] is False

    missing = home / "missing_source"
    shutil.copytree(attempt, missing, copy_function=os.link)
    (missing / "original-turn-signal.json").unlink()
    _, missing_proof = processing(case, missing, home / "source_feedback", VALIDATOR, env)
    feedback = json.loads((home / "source_feedback/v0001/feedback.json").read_text())
    assert missing_proof["recorded_only"] is True and missing_proof["missing_evidence"] is True
    assert missing_proof["originals_preserved"] is True
    assert feedback["classification"] == "incomplete_or_unavailable_law_evidence"
    assert "Missing required source: original-turn-signal.json" in feedback["error"]
    assert feedback["native_replay_requested"] is False

    bad_validator = home / "absent-validator"
    failed, _ = processing(case, attempt, home / "validator_feedback", bad_validator, env,
                           expected=None)
    assert failed.returncode != 0
    failed_feedback = json.loads((home / "validator_feedback/v0001/feedback.json").read_text())
    assert failed_feedback["recorded_only"] is True
    assert failed_feedback["native_replay_requested"] is False
    assert failed_feedback["error"]
    print(f"{tag}: positive saved processing; missing source feedback; missing validator feedback")


if __name__ == "__main__":
    main()
