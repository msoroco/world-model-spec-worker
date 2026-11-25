"""Rebuild six selected analyses from current-runtime recorded-only acquisitions."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1]
MANIFEST = PACKAGE / "execution-manifest.json"
DECODER = REPO / ".runtime-work/c215286-current-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def run():
    manifest = json.loads(MANIFEST.read_text())
    if len(manifest["cases"]) != 6:
        raise ValueError("Six selected cases required")
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.split("__")[-1]
        source = REPO / ".runtime-work/c215286-current-runtime-reproof" / suffix / "primary/compatibility"
        replay = REPO / ".runtime-work/c215286-current-runtime-saved" / suffix / "source"
        output = REPO / ".runtime-work/c215286-current-runtime-saved" / suffix / "output"
        if not replay.exists():
            replay.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, replay, copy_function=shutil.copy2)
            (replay / "candidate-selection.json").unlink()
        if sha(replay / "construction.json") != entry["construction_sha256"]:
            raise ValueError("Current construction changed: " + case_id)
        cmd = [sys.executable, str(REPO / "runtime.py"), "process-saved",
               "--manifest", str(MANIFEST), "--case", case_id, "--attempt", str(replay),
               "--output", str(output), "--library", str(REPO / "runtime/library"),
               "--validator", str(DECODER)]
        command_log = PACKAGE / "cases" / (suffix + "-current-runtime-saved-command.log")
        receipts = sorted(output.glob("v*/processing.json"))
        if not receipts:
            with command_log.open("w") as log:
                result = subprocess.run(cmd, cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
                                        timeout=900, check=False)
            if result.returncode:
                raise RuntimeError("Current saved-source reanalysis failed: " + case_id)
            receipts = sorted(output.glob("v*/processing.json"))
        if not receipts:
            raise ValueError("Saved receipt missing: " + case_id)
        value = json.loads(receipts[-1].read_text())
        if not (value["passed"] and value["recorded_only"] and value["originals_preserved"]
                and not value["missing_evidence"] and value["case_id"] == case_id
                and value["analysis_revision"]["construction_sha256"] == entry["construction_sha256"]):
            raise ValueError("Saved receipt differs from current construction: " + case_id)
        returned = PACKAGE / "cases" / (suffix + "-current-runtime-saved-receipt.json")
        shutil.copy2(receipts[-1], returned)
        if not command_log.is_file():
            shutil.copy2(output / "v0001/analysis.log", command_log)
        entry["saved_processing"] = {"command": " ".join(cmd), "receipt": "cases/" + returned.name,
                                     "sha256": sha(returned), "log": "cases/" + command_log.name,
                                     "log_sha256": sha(command_log)}
        write(MANIFEST, manifest)
        print(suffix, "current-runtime recorded-only saved processing passed", flush=True)


if __name__ == "__main__":
    run()
