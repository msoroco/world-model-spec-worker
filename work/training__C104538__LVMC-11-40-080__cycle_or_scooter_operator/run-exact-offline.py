"""Run all eight exact mounted-bicycle bundles with pinned offline CLI."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE/"draft-exact-execution-manifest.json"
PYTHON = ROOT/".venv-cpu/bin/python"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["status"] == "draft_not_selected" and len(manifest["cases"]) == 2
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = str(ROOT/".runtime-work/geos-wheel/shapely.libs")+os.pathsep+env.get("LD_LIBRARY_PATH", "")
    scratch = Path(tempfile.mkdtemp(dir=ROOT/".runtime-work", prefix="c104538-lvmc-offline-"))
    receipts = []
    for entry in manifest["cases"]:
        kind = "mounted_obey" if entry["case_id"].endswith("__controlled_1") else "mounted_turn"
        for name in ("primary", "fallback1", "fallback2", "fallback3"):
            ref = entry if name == "primary" else next(x for x in entry["candidates"] if x["id"] == name)
            target = scratch/(kind+"-"+name)
            command = [str(PYTHON), str(ROOT/"runtime.py"), "offline", "--manifest", str(MANIFEST),
                       "--case", entry["case_id"], "--candidate", name,
                       "--output", str(target), "--python", str(PYTHON)]
            result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
            directory = HERE/"draft-exact-candidates"/kind/name
            log = directory/"command.log"
            log.write_text(result.stdout)
            unit = target/"offline.log"
            retained = directory/"unit-test.log"
            if unit.is_file():
                shutil.copyfile(unit, retained)
            receipt = {"case_id": entry["case_id"], "candidate_id": name,
                       "exit_code": result.returncode, "construction_sha256": ref["construction_sha256"],
                       "command_log": log.relative_to(HERE).as_posix(),
                       "command_log_sha256": sha(log),
                       "unit_log": retained.relative_to(HERE).as_posix() if retained.is_file() else None,
                       "unit_log_sha256": sha(retained) if retained.is_file() else None,
                       "selected": False, "simulation_started": False}
            (directory/"offline-receipt.json").write_text(json.dumps(receipt, indent=2)+"\n")
            receipts.append(receipt)
            print(kind, name, result.returncode, flush=True)
    summary = {"format": "c104538-lvmc-exact-offline-summary-v1",
               "manifest_sha256": sha(MANIFEST), "results": receipts,
               "passed": all(x["exit_code"] == 0 for x in receipts),
               "original_native_capture_executed": False, "selected": False}
    (HERE/"draft-exact-offline-summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
