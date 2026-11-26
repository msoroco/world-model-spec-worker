"""Check recorded-only saved processing for every exact diagnostic case."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PRIVATE = REPO / ".runtime-work/c412593-nov26"
MANIFEST = ROOT / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c111125-owner/validator/.lake/build/bin/adapterCheck"


def main() -> None:
    if Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve() != PRIVATE.resolve():
        raise ValueError("Use the C412593 private runtime output root")
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, TMPDIR=str(PRIVATE), PYTHONDONTWRITEBYTECODE="1")
    receipts = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        tag = case.rsplit("__", 1)[-1]
        attempt = PRIVATE / ("saved-compat-" + tag + "-reviewed")
        output = PRIVATE / ("saved-" + tag + "-reviewed")
        compat = [sys.executable, str(REPO / "runtime.py"), "compatibility",
                  "--manifest", str(MANIFEST), "--case", case,
                  "--output", str(attempt), "--library", str(REPO / "runtime/library"),
                  "--validator", str(VALIDATOR)]
        fresh = subprocess.run(compat, cwd=REPO, env=env, text=True,
                               capture_output=True, check=False, timeout=300)
        if fresh.returncode:
            raise RuntimeError(f"fresh compatibility {tag}: {fresh.stderr[-2000:]}")
        command = [sys.executable, str(REPO / "runtime.py"), "process-saved",
                   "--manifest", str(MANIFEST), "--case", case,
                   "--attempt", str(attempt), "--output", str(output),
                   "--library", str(REPO / "runtime/library"),
                   "--validator", str(VALIDATOR)]
        run = subprocess.run(command, cwd=REPO, env=env, text=True,
                             capture_output=True, check=False, timeout=300)
        if run.returncode:
            raise RuntimeError(f"saved {tag}: {run.stderr[-2000:]}")
        proof = json.loads((output / "v0001/processing.json").read_text())
        if (proof.get("recorded_only") is not True or proof.get("passed") is not True
                or proof.get("missing_evidence") is not False
                or proof.get("originals_preserved") is not True
                or proof.get("final_video_checks", {}).get("passed") is not True):
            raise ValueError("Saved processing proof incomplete: " + tag)
        receipts.append({"case_id": case, "recorded_only": True,
                         "originals_preserved": True, "final_video_decode": True,
                         "physical_acceptance_claimed": False})
        print(tag, flush=True)
    (ROOT / "saved-processing-receipts.json").write_text(
        json.dumps(receipts, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
