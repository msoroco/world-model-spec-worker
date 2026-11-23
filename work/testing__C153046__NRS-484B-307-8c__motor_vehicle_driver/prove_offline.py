"""Run the pinned CPU offline entrypoint for all eight exact constructions."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

from build_case_plan import AID, KINDS

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main() -> None:
    root = REPO / ".runtime-work" / ("c153046-offline-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    manifest = ROOT / "execution-manifest.draft.json"
    results = []
    for suffix in KINDS:
        case_id = AID + "__" + suffix
        output = root / suffix
        command = [sys.executable, str(REPO / "runtime.py"), "offline", "--manifest",
                   str(manifest), "--case", case_id, "--output", str(output)]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        completed = subprocess.run(command, cwd=REPO, env=env, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = output / "offline.log"
        results.append({"case_id": case_id, "command": command, "exit_code": completed.returncode,
                        "runtime_output": completed.stdout,
                        "offline_log": str(log.relative_to(REPO)) if log.exists() else None,
                        "offline_log_sha256": hashlib.sha256(log.read_bytes()).hexdigest() if log.exists() else None})
    receipt = {"format": "c153046-eight-case-offline-proof", "manifest": str(manifest.relative_to(REPO)),
               "construction_hashes": {entry["case_id"]: entry["construction_sha256"]
                                       for entry in json.loads(manifest.read_text())["cases"]},
               "all_passed": all(row["exit_code"] == 0 for row in results), "results": results,
               "physical_realization_claimed": False}
    (ROOT / "cpu-offline-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
    for row in results:
        print(row["case_id"], "exit", row["exit_code"], row["offline_log_sha256"])
        if row["exit_code"]:
            print(row["runtime_output"])
    if not receipt["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
