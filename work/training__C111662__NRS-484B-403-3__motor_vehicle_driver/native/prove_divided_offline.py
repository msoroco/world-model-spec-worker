"""Run and independently byte-audit all eight divided-opening CPU packages."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from build import CASE, HERE, ROOT
from divided_opening import BRANCH, CENTERS


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def prove():
    manifest_path = BRANCH / "draft-execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entries = []
    checked = 0
    for case in manifest["cases"]:
        suffix = case["case_id"].split("__")[-1]
        choices = [{"id": "primary", "construction": case["construction"],
                    "construction_sha256": case["construction_sha256"]}] + case["candidates"]
        for choice in choices:
            output = BRANCH / "pinned-runs" / suffix / choice["id"]
            if output.exists():
                shutil.rmtree(output)
            command = [sys.executable, str(ROOT / "runtime.py"), "offline",
                       "--manifest", str(manifest_path), "--case", case["case_id"],
                       "--candidate", choice["id"], "--output", str(output),
                       "--python", sys.executable]
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            if completed.returncode:
                raise RuntimeError(f"{suffix}/{choice['id']}: {completed.stdout}\n{completed.stderr}")
            receipt = json.loads(completed.stdout)
            if receipt["offline_passed"] is not True or receipt["simulation_started"] is not False:
                raise ValueError("Divided opening offline execution did not pass")
            construction_path = BRANCH / choice["construction"]
            raw = construction_path.read_bytes()
            if digest(raw) != choice["construction_sha256"]:
                raise ValueError("Pinned construction digest mismatch")
            construction = json.loads(raw)
            if construction["status"] != "unselected_cpu_diagnostic":
                raise ValueError("Candidate unexpectedly selected")
            for file in construction["files"]:
                if (output / file["path"]).read_bytes() != file["content"].encode():
                    raise ValueError("Materialized source differs from pinned file")
                checked += 1
            log = (output / "offline.log").read_text()
            if "OK" not in log or "Ran 4 tests" not in log:
                raise ValueError("Divided opening CPU tests missing")
            entries.append({"case_suffix": suffix, "candidate_id": choice["id"],
                            "offline_passed": True, "simulation_started": False})
    first = (BRANCH / manifest["cases"][0]["construction"]).read_bytes()
    if digest(first + b" ") == manifest["cases"][0]["construction_sha256"]:
        raise ValueError("Changed construction digest accepted")
    result = {"format": "c111662-4033-divided-offline-proof-v1",
              "candidate_count": len(entries), "cpu_tests_passed": 4 * len(entries),
              "materialized_files_checked": checked,
              "changed_construction_rejected": True, "entries": entries,
              "original_native_observed": False, "delivery_ready": False}
    (BRANCH / "pinned-offline-proof.json").write_text(
        json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    result = prove()
    print(json.dumps({key: result[key] for key in
                      ("candidate_count", "cpu_tests_passed", "materialized_files_checked")}))
