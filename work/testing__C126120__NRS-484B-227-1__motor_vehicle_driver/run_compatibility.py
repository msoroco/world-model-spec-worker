"""Run pinned primary/fallback diagnostic compatibility and retain real receipts."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(manifest):
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


def main():
    manifest = json.loads(MANIFEST.read_text())
    failures = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        folder = HERE / "cases" / suffix
        for candidate_id in ("primary", "fallback1"):
            output = REPO / ".runtime-work/c126120-compat-batch" / suffix / candidate_id
            revision = 1
            while output.exists():
                output = REPO / ".runtime-work/c126120-compat-batch" / suffix / f"{candidate_id}-{revision}"
                revision += 1
            command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                       "compatibility", "--manifest", str(MANIFEST), "--case", entry["case_id"],
                       "--candidate", candidate_id, "--output", str(output),
                       "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
            proc = subprocess.run(command, cwd=REPO, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                  text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            command_log = folder / f"{candidate_id}-compat-command.log"
            command_log.write_text(proc.stdout)
            if proc.returncode:
                failures.append((suffix, candidate_id, proc.stdout[-500:].replace("\n", " ")))
                print(suffix, candidate_id, "FAILED", proc.stdout.splitlines()[-1], flush=True)
                continue
            receipt = folder / f"{candidate_id}-compatibility.json"
            analysis = folder / f"{candidate_id}-compat-analysis.log"
            negative = folder / f"{candidate_id}-compat-negative.log"
            shutil.copyfile(output / "compatibility.json", receipt)
            shutil.copyfile(output / "compatibility-analysis.log", analysis)
            shutil.copyfile(output / "negative-analysis.log", negative)
            spec = {"receipt": str(receipt.relative_to(HERE)), "sha256": sha(receipt),
                    "log": str(analysis.relative_to(HERE)), "negative_log": str(negative.relative_to(HERE)),
                    "command": " ".join(command), "exit_code": 0,
                    "command_log": str(command_log.relative_to(HERE)), "command_log_sha256": sha(command_log)}
            if candidate_id == "primary":
                entry["compatibility"] = spec
                entry["negative"] = {"log": str(negative.relative_to(HERE)), "sha256": sha(negative)}
            else:
                entry["candidates"][0]["compatibility"] = spec
            save(manifest)
            print(suffix, candidate_id, "passed full pinned compatibility", flush=True)
    if failures:
        print("Failures:", json.dumps(failures, indent=2), flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
