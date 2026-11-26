"""Run and bind exact primary compatibility proofs for every selected case."""

from __future__ import annotations

from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
PRIVATE = REPO / ".runtime-work/c177008-owner-nov26/output"
VALIDATOR = REPO / ".runtime-work/c111125-owner/validator/.lake/build/bin/adapterCheck"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def copy_text(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", choices=("primary", "fallback1"), required=True)
    candidate = parser.parse_args().candidate
    if Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve() != PRIVATE.resolve():
        raise ValueError("Use the C177008 private runtime output root")
    if not VALIDATOR.is_file():
        raise ValueError("Pinned CPU validator missing")
    env = dict(os.environ, TMPDIR=str(PRIVATE), PYTHONDONTWRITEBYTECODE="1")
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        tag = case.rsplit("__", 1)[-1]
        output = PRIVATE / ("compat-" + tag + "-" + candidate + "-reviewed2")
        command = [sys.executable, str(REPO / "runtime.py"), "compatibility",
                   "--manifest", str(MANIFEST), "--case", case,
                   "--output", str(output), "--library", str(REPO / "runtime/library"),
                   "--validator", str(VALIDATOR), "--candidate", candidate]
        run = subprocess.run(command, cwd=REPO, env=env, text=True,
                             capture_output=True, check=False, timeout=300)
        work = ROOT / "cases" / tag / ("compatibility" if candidate == "primary"
                                         else "fallback1-compatibility")
        work.mkdir(parents=True, exist_ok=True)
        command_log = work / "command.log"
        command_log.write_text((run.stdout + run.stderr).rstrip() + "\n")
        if run.returncode:
            raise RuntimeError(f"compatibility {tag}: {run.stderr[-2000:]}")
        receipt = json.loads((output / "compatibility.json").read_text())
        if not receipt.get("passed") or receipt.get("case_id") != case:
            raise ValueError("Wrong compatibility receipt")
        proof = work / "compatibility.json"
        positive_log = work / "positive.log"
        negative_log = work / "negative-analysis.log"
        copy_text(output / "compatibility.json", proof)
        copy_text(output / "compatibility-analysis.log", positive_log)
        copy_text(output / "negative-analysis.log", negative_log)
        if digest(positive_log) != receipt["log_sha256"]:
            raise ValueError("Positive log changed while copying")
        if digest(negative_log) != receipt["negative_log_sha256"]:
            raise ValueError("Negative log changed while copying")
        if candidate == "primary":
            entry["compatibility"] = {"receipt": proof.relative_to(ROOT).as_posix(),
                                       "sha256": digest(proof),
                                       "log": positive_log.relative_to(ROOT).as_posix()}
            entry["negative"] = {"log": negative_log.relative_to(ROOT).as_posix()}
        else:
            entry["candidates"][0]["compatibility"] = {
                "receipt": proof.relative_to(ROOT).as_posix(),
                "sha256": digest(proof),
                "log": positive_log.relative_to(ROOT).as_posix(),
                "negative_log": negative_log.relative_to(ROOT).as_posix()}
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(tag, flush=True)


if __name__ == "__main__":
    main()
