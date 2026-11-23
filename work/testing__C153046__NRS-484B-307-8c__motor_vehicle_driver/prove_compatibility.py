"""Run and retain pinned positive/negative diagnostic compatibility per exact case."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from build_case_plan import AID, KINDS

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if not VALIDATOR.is_file():
        raise ValueError("pinned Lean decoder must be built before compatibility")
    manifest = json.loads(MANIFEST.read_text())
    by_case = {entry["case_id"]: entry for entry in manifest["cases"]}
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    for suffix in KINDS:
        case_id = AID + "__" + suffix
        entry = by_case[case_id]
        destination = REPO / ".runtime-work" / ("c153046-compatibility-" + run_id) / suffix
        command = [sys.executable, str(REPO / "runtime.py"), "compatibility",
                   "--manifest", str(MANIFEST), "--case", case_id,
                   "--output", str(destination), "--library", str(REPO / "runtime/library"),
                   "--validator", str(VALIDATOR)]
        folder = ROOT / "diagnostics" / suffix
        command_log = folder / "compat-command.log"
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        with command_log.open("w") as stream:
            process = subprocess.run(command, cwd=REPO, env=env, stdout=stream,
                                     stderr=subprocess.STDOUT, timeout=900)
        if process.returncode:
            raise ValueError("pinned compatibility failed: " + suffix +
                             "; inspect " + str(command_log.relative_to(REPO)))
        receipt_path = folder / "compatibility.json"
        analysis_path = folder / "compat-analysis.log"
        negative_path = folder / "negative-analysis.log"
        shutil.copyfile(destination / "compatibility.json", receipt_path)
        shutil.copyfile(destination / "compatibility-analysis.log", analysis_path)
        shutil.copyfile(destination / "negative-analysis.log", negative_path)
        receipt = json.loads(receipt_path.read_text())
        if receipt.get("passed") is not True or receipt["case_id"] != case_id:
            raise ValueError("compatibility receipt identity differs: " + suffix)
        entry["compatibility"] = {"command": " ".join(command),
                                   "receipt": str(receipt_path.relative_to(ROOT)),
                                   "sha256": sha(receipt_path),
                                   "log": str(analysis_path.relative_to(ROOT)),
                                   "negative_log": str(negative_path.relative_to(ROOT))}
        entry["negative"] = {"log": str(negative_path.relative_to(ROOT)),
                              "sha256": sha(negative_path)}
        entry["proof_status"] = "diagnostic_compatibility_passed_physical_pending"
        print("pinned positive/negative compatibility passed", suffix, flush=True)
    manifest["status"] = "diagnostic_compatibility_passed_other_delivery_gates_pending"
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
