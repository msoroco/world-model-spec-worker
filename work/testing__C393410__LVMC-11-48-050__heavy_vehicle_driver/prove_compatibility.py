"""Run all twenty-six selected current-runtime diagnostic compatibility checks."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main():
    manifest = ROOT / "execution-manifest.draft.json"
    entries = json.loads(manifest.read_text())["cases"]
    output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "/nonexistent")).resolve()
    if REPO / ".runtime-work" not in output_root.parents:
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    results = []
    for entry in entries:
        for candidate in ("primary", "fallback1"):
            short = entry["case_id"].split("__")[-1]
            dest = REPO / ".runtime-work" / "c393410-050/compat-selected" / short / candidate
            if dest.exists():
                shutil.rmtree(dest)
            command = [str(REPO / ".venv-cpu/bin/python"),
                str(ROOT / "run_compat_deterministic.py"), "--manifest", str(manifest),
                "--case", entry["case_id"], "--candidate", candidate,
                "--output", str(dest), "--library", str(REPO / "runtime/library"),
                "--validator", str(REPO / ".runtime-work/c150911-decoder/.lake/build/bin/adapterCheck")]
            completed = subprocess.run(command, capture_output=True, text=True,
                                       env=os.environ)
            row = {"case_id": entry["case_id"], "candidate": candidate,
                   "exit_code": completed.returncode,
                   "command": " ".join(command),
                   "output": str(dest.relative_to(REPO))}
            if completed.returncode == 0:
                receipt = json.loads((dest / "compatibility.json").read_text())
                folder = ROOT / "cases" / short
                prefix = "proof-compatibility-" + candidate
                for source, target, key in (("compatibility-analysis.log", prefix + "-analysis.log", "log_sha256"),
                                            ("negative-analysis.log", prefix + "-negative.log", "negative_log_sha256")):
                    raw = (dest / source).read_bytes().rstrip() + b"\n"
                    (folder / target).write_bytes(raw)
                    receipt[key] = hashlib.sha256(raw).hexdigest()
                (folder / (prefix + ".json")).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
                saved = folder / (prefix + ".json")
                row.update({"receipt": str(saved.relative_to(ROOT)),
                    "receipt_sha256": hashlib.sha256(saved.read_bytes()).hexdigest(),
                    "positive_log": str((folder / (prefix + "-analysis.log")).relative_to(ROOT)),
                    "negative_log": str((folder / (prefix + "-negative.log")).relative_to(ROOT)),
                    "construction_sha256": receipt["construction_sha256"]})
            else:
                row["error"] = (completed.stdout + completed.stderr)[-1600:]
            results.append(row)
            print(short, candidate, completed.returncode, flush=True)
    (ROOT / "cpu-compatibility-proofs.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n")
    if any(row["exit_code"] for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
