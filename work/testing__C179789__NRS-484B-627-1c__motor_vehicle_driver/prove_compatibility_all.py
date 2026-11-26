"""Run exact pinned software compatibility for all route cases and candidates."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c111125-owner/validator/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", choices=("primary", "fallback1"), required=True)
    candidate = parser.parse_args().candidate
    output_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if REPO / ".runtime-work" not in output_root.parents:
        raise ValueError("compatibility output must be under .runtime-work")
    if not VALIDATOR.is_file():
        raise ValueError("pinned CPU validator missing")
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        tag = case_id.rsplit("__", 1)[-1]
        output = output_root / ("compat-" + tag + "-" + candidate + "-v3")
        if output.exists():
            raise ValueError("compatibility output already exists: " + str(output))
        command = [sys.executable, str(REPO / "runtime.py"), "compatibility",
                   "--manifest", str(MANIFEST), "--case", case_id,
                   "--output", str(output), "--library", str(REPO / "runtime/library"),
                   "--validator", str(VALIDATOR), "--candidate", candidate]
        run = subprocess.run(command, cwd=REPO, text=True, capture_output=True,
                             timeout=300)
        folder = ROOT / "cases" / tag / ("compatibility" if candidate == "primary"
                                         else "fallback1-compatibility")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "command.log").write_text((run.stdout + run.stderr).rstrip() + "\n")
        if run.returncode:
            raise RuntimeError("compatibility failed " + tag + "/" + candidate + ": " + run.stderr[-2000:])
        receipt = json.loads((output / "compatibility.json").read_text())
        for source_name, target_name in (("compatibility.json", "compatibility.json"),
                                         ("compatibility-analysis.log", "positive.log"),
                                         ("negative-analysis.log", "negative-analysis.log")):
            (folder / target_name).write_bytes((output / source_name).read_bytes())
        proof = folder / "compatibility.json"
        positive = folder / "positive.log"
        negative = folder / "negative-analysis.log"
        if sha(positive) != receipt["log_sha256"] or sha(negative) != receipt["negative_log_sha256"]:
            raise ValueError("copied route compatibility log differs")
        if candidate == "primary":
            entry["compatibility"] = {"receipt": proof.relative_to(ROOT).as_posix(),
                                       "sha256": sha(proof),
                                       "log": positive.relative_to(ROOT).as_posix()}
            entry["negative"] = {"log": negative.relative_to(ROOT).as_posix()}
        else:
            entry["candidates"][0]["compatibility"] = {
                "receipt": proof.relative_to(ROOT).as_posix(), "sha256": sha(proof),
                "log": positive.relative_to(ROOT).as_posix(),
                "negative_log": negative.relative_to(ROOT).as_posix()}
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(tag, candidate, flush=True)


if __name__ == "__main__":
    main()
