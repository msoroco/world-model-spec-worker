"""Guarded canonical fallback preparation for an ordered GPU queue row."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    if len(sys.argv) != 3 or sys.argv[2] not in ("fallback1", "fallback2", "fallback3"):
        raise SystemExit("Usage: prepare-delivery-candidate.py CASE_ID FALLBACK_ID")
    case_id, candidate = sys.argv[1:]
    queue = json.loads((ROOT / "work/_shared/gpu-queue.json").read_text())
    matches = [row for row in queue["cases"] if row["case_id"] == case_id]
    if len(matches) != 1:
        raise SystemExit("Case missing or duplicated in ordered GPU queue")
    row = matches[0]
    if row["status"] != "ready" or row["dispatchable"] is not True:
        raise SystemExit("Queue case is not released for GPU preparation")
    database = os.environ.get("WORKER_DB")
    if not database:
        raise SystemExit("WORKER_DB is required")
    subprocess.run([sys.executable, str(ROOT / "worker_check.py"), "--complete",
                    "--require-delivery-ready"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-m", "worker_exchange", "prepare-delivery",
                    "--repo", str(ROOT), "--batch", queue["batch_id"], "--db", database,
                    "--assignment", row["assignment_id"], "--case", case_id,
                    "--candidate", candidate], cwd=ROOT,
                   env={**os.environ, "PYTHONPATH": str(ROOT / "runtime/pipeline/scenario_pipeline")},
                   check=True)


if __name__ == "__main__":
    main()
