"""Run the pinned offline command for every exact C179789 construction."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUTPUT_ROOT = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""))
if not OUTPUT_ROOT.is_absolute() or not OUTPUT_ROOT.is_relative_to(REPO / ".runtime-work"):
    raise SystemExit("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "partial_cpu_construction_only":
        raise ValueError("expected unproved construction manifest")
    output = HERE / "offline"
    output.mkdir(exist_ok=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        construction = HERE / entry["construction"]
        if sha(construction) != entry["construction_sha256"]:
            raise ValueError("stale construction: " + suffix)
        container = Path(tempfile.mkdtemp(prefix="offline-" + suffix + "-", dir=OUTPUT_ROOT))
        attempt = container / "bundle"
        command = [sys.executable, str(REPO / "runtime.py"), "offline",
                   "--manifest", str(manifest_path), "--case", case_id,
                   "--output", str(attempt), "--python", sys.executable]
        completed = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                                   timeout=360, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        if completed.returncode:
            detail = (attempt / "offline.log")
            raise ValueError("pinned offline failed for " + suffix + ": " +
                             (detail.read_text()[-1000:] if detail.is_file()
                              else completed.stderr[-1000:]))
        log = attempt / "offline.log"
        text = log.read_text(encoding="utf-8")
        counts = re.findall(r"Ran (\d+) tests?", text)
        if not counts or int(counts[-1]) < 47 or "OK" not in text or '"bundle_checked": true' not in text:
            raise ValueError("offline evidence incomplete: " + suffix)
        test_count = int(counts[-1])
        retained = output / (suffix + ".log")
        shutil.copyfile(log, retained)
        entry["offline"] = {
            "command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline "
                       "--manifest work/" + HERE.name + "/execution-manifest.json "
                       "--case " + case_id + " --output .runtime-work/<fresh>/bundle "
                       "--python $PWD/.venv-cpu/bin/python",
            "exit_code": 0, "construction_sha256": entry["construction_sha256"],
            "log": retained.relative_to(HERE).as_posix(),
            "log_sha256": sha(retained), "test_count": test_count,
            "diagnostic_fixture": True, "physical_acceptance_claimed": False,
        }
        print(json.dumps({"case_id": case_id, "tests": test_count,
                          "log_sha256": sha(retained)}, sort_keys=True), flush=True)
    manifest["status"] = "partial_offline_cpu_proved_compatibility_pending"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
