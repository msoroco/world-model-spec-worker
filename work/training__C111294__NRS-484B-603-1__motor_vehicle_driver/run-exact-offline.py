"""Run eight C111294 NRS 484B.603(1) bundles through pinned offline CLI."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "draft-execution-manifest.json"
PYTHON = ROOT / ".venv-cpu/bin/python"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    data = json.loads(MANIFEST.read_text())
    if data["status"] != "draft_not_selected" or len(data["cases"]) != 2:
        raise ValueError("Only two unselected approach cases may run here")
    env = dict(os.environ)
    geos = str(ROOT / ".runtime-work/geos-wheel/shapely.libs")
    env["LD_LIBRARY_PATH"] = geos + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    run_root = Path(tempfile.mkdtemp(dir=ROOT / ".runtime-work",
                                     prefix="c111294-approach-offline-"))
    receipts = []
    for entry in data["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            destination = run_root / (suffix + "-" + candidate)
            command = [str(PYTHON), str(ROOT / "runtime.py"), "offline",
                       "--manifest", str(MANIFEST), "--case", entry["case_id"],
                       "--candidate", candidate, "--output", str(destination),
                       "--python", str(PYTHON)]
            result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    timeout=300)
            folder = HERE / "exact-drafts" / suffix / candidate
            log = folder / "command-proof.log"
            log.write_text(result.stdout)
            selected = entry if candidate == "primary" else next(
                c for c in entry["candidates"] if c["id"] == candidate)
            receipt = {"case_id": entry["case_id"], "candidate_id": candidate,
                       "command": command, "exit_code": result.returncode,
                       "construction_sha256": selected["construction_sha256"],
                       "offline_command_log_sha256": sha(log),
                       "scope": "unselected exact pinned offline only; no portable or physical proof"}
            unit = destination / "offline.log"
            if unit.is_file():
                shutil.copyfile(unit, folder / "unit-proof.log")
                receipt["offline_test_log_sha256"] = sha(folder / "unit-proof.log")
            (folder / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
            receipts.append(receipt)
            print(suffix, candidate, result.returncode, flush=True)
    summary = {"format": "unselected-exact-offline-summary-v1",
               "runtime_manifest_sha256": data["runtime_manifest_sha256"],
               "manifest_sha256": sha(MANIFEST), "results": receipts,
               "all_passed": all(r["exit_code"] == 0 for r in receipts),
               "selected": False}
    (HERE / "exact-offline-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    if not summary["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
