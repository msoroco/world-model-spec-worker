"""Rerun the eight exact construction offline checks."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.draft.json"
OUTPUT = REPO / ".runtime-work/c150911-owner/offline-selected-v2"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        short = case_id.split("__")[-1]
        for candidate in ("primary", "fallback1"):
            construction = entry if candidate == "primary" else entry["candidates"][0]
            output = OUTPUT / short / candidate
            command = [sys.executable, str(REPO / "runtime.py"), "offline",
                       "--manifest", str(MANIFEST), "--case", case_id,
                       "--candidate", candidate, "--output", str(output),
                       "--python", sys.executable]
            env = dict(os.environ)
            env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(REPO / ".runtime-work/c150911-output")
            env["TMPDIR"] = str(REPO / ".runtime-work/c150911-tmp")
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            Path(env["TMPDIR"]).mkdir(parents=True, exist_ok=True)
            completed = subprocess.run(command, cwd=REPO, env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True)
            log = ROOT / "cases" / short / f"proof-offline-{candidate}.log"
            log.write_text(completed.stdout.rstrip() + "\n", encoding="utf-8")
            row = {"case_id": case_id, "candidate": candidate,
                   "construction_sha256": construction["construction_sha256"],
                   "command": " ".join(command), "exit_code": completed.returncode,
                   "log": str(log.relative_to(ROOT)), "log_sha256": sha(log)}
            rows.append(row)
            print(short, candidate, completed.returncode, flush=True)
            if completed.returncode:
                break
        if rows[-1]["exit_code"]:
            break
    (ROOT / "cpu-offline-proofs.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if len(rows) != 8 or any(row["exit_code"] for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
