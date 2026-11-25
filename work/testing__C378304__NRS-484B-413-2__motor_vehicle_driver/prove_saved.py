"""Run exact diagnostic acquisition through recorded-only processing."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    tag = args.case.rsplit("__", 1)[-1]
    scratch = Path(tempfile.mkdtemp(prefix="saved-proof-" + tag + "-",
                                     dir=REPO / ".runtime-work/c378304"))
    attempt = scratch / "attempt"
    derived = scratch / "derived"
    validator = REPO / ".runtime-work/c111125-owner/validator/.lake/build/bin/adapterCheck"
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / ".runtime-work/c378304"))
    common = [sys.executable, str(REPO / "runtime.py")]
    first = common + ["compatibility", "--manifest", str(MANIFEST), "--case", args.case,
                      "--output", str(attempt), "--library", str(REPO / "runtime/library"),
                      "--validator", str(validator)]
    with (scratch / "compatibility.log").open("w") as log:
        subprocess.run(first, cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT,
                       check=True, timeout=300)
    second = common + ["process-saved", "--manifest", str(MANIFEST), "--case", args.case,
                       "--attempt", str(attempt), "--output", str(derived),
                       "--library", str(REPO / "runtime/library"), "--validator", str(validator)]
    with (scratch / "process-saved.log").open("w") as log:
        subprocess.run(second, cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT,
                       check=True, timeout=300)
    receipt = json.loads((derived / "v0001/processing.json").read_text())
    if (receipt.get("recorded_only") is not True or receipt.get("passed") is not True or
            receipt.get("missing_evidence") is not False or
            receipt.get("originals_preserved") is not True or
            receipt.get("final_video_checks", {}).get("passed") is not True):
        raise AssertionError("saved-only source processing failed")
    print(json.dumps({"case_id": args.case, "recorded_only": True,
                      "originals_preserved": True, "final_video_decode": True,
                      "physical_acceptance_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
