"""Replay four staged diagnostic acquisitions through recorded-only processing."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1]
STAGE = ROOT / ".runtime-work/c215286-intersection-stage/manifest.json"
DECODER = ROOT / ".runtime-work/c215286-current-decoder/.lake/build/bin/adapterCheck"
ROWS = (
    ("intersection-entry", "reverse_into_intersection", "c215286-alt-intersection-compat-v4"),
    ("intersection-stop", "reverse_stops_before_intersection", "c215286-alt-intersection-stop-compat"),
    ("corner-entry", "reverse_around_street_corner", "c215286-alt-corner-entry-compat-v3"),
    ("corner-stop", "reverse_stops_before_street_corner", "c215286-alt-corner-stop-compat"),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    manifest = json.loads(STAGE.read_text())
    entries = {row["case_id"]: row for row in manifest["cases"]}
    index = {"format": "worker-staged-saved-processing-index",
             "scope": "Four synthetic 900-frame recorded-only reanalyses; no Native or legal acceptance",
             "cases": []}
    for label, suffix, source_name in ROWS:
        case_id = PACKAGE.name + "__" + suffix
        entry = entries[case_id]
        source = ROOT / ".runtime-work" / source_name
        replay = ROOT / ".runtime-work" / ("c215286-alt-" + label + "-saved-source")
        output = ROOT / ".runtime-work" / ("c215286-alt-" + label + "-saved-full")
        if not replay.exists():
            shutil.copytree(source, replay, copy_function=shutil.copy2)
            (replay / "candidate-selection.json").unlink()
        construction = replay / "construction.json"
        if sha(construction) != entry["construction_sha256"]:
            raise ValueError("Diagnostic construction changed: " + case_id)
        cmd = [sys.executable, str(ROOT / "runtime.py"), "process-saved",
               "--manifest", str(STAGE), "--case", case_id, "--attempt", str(replay),
               "--output", str(output), "--library", str(ROOT / "runtime/library"),
               "--validator", str(DECODER)]
        log = PACKAGE / "cases" / (label + "-saved-processing.log")
        if label != "intersection-entry" or not list(output.glob("v*/processing.json")):
            with log.open("w") as stream:
                completed = subprocess.run(cmd, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                           timeout=900, check=False)
            if completed.returncode:
                raise RuntimeError(case_id + " recorded-only processing failed; see " + str(log))
        else:
            previous = ROOT / ".runtime-work/c215286-alt-intersection-saved-full.log"
            shutil.copy2(previous, log)
        receipts = sorted(output.glob("v*/processing.json"))
        if not receipts:
            raise ValueError("Missing saved-processing receipt: " + case_id)
        receipt = receipts[-1]
        value = json.loads(receipt.read_text())
        if not (value["passed"] and value["recorded_only"] and value["originals_preserved"]
                and not value["missing_evidence"] and value["timestamp_joins"]["frames"] == 900):
            raise ValueError("Incomplete saved-processing receipt: " + case_id)
        returned = PACKAGE / "cases" / (label + "-saved-processing-receipt.json")
        shutil.copy2(receipt, returned)
        index["cases"].append({"case_id": case_id, "receipt": returned.name,
                               "receipt_sha256": sha(returned), "log": log.name,
                               "log_sha256": sha(log), "frames": 900, "passed": True})
        print(label, "recorded-only processing passed", flush=True)
    destination = PACKAGE / "cases/alternative-full-saved-processing-index.json"
    destination.write_text(json.dumps(index, indent=2) + "\n")


if __name__ == "__main__":
    run()
