"""Run each exact selected case through current public compatibility checks.

This writes compact source-bound receipts and logs under the assignment. The
generated full diagnostic fixtures remain under ignored .runtime-work/.
"""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "selected-preflight-manifest.json"
VALIDATOR = REPO / ".runtime-work" / "nrs280-decoder" / ".lake" / "build" / "bin" / "adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_text(path, text):
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
    scratch.mkdir(parents=True, exist_ok=True)
    temp = scratch / (path.name + ".staging")
    temp.write_text(text.rstrip() + "\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temp, path)


def next_output(suffix):
    base = REPO / ".runtime-work"
    for number in range(1, 100):
        path = base / f"c111271-selected-{suffix}-compat-v{number}"
        if not path.exists():
            return path
    raise RuntimeError("No fresh compatibility path for " + suffix)


def run(entry):
    suffix = entry["case_id"].rsplit("__", 1)[-1]
    output = next_output(suffix)
    command = [sys.executable, "-B", str(REPO / "runtime.py"), "compatibility",
               "--manifest", str(MANIFEST), "--case", entry["case_id"],
               "--output", str(output), "--library", str(REPO / "runtime" / "library"),
               "--validator", str(VALIDATOR)]
    completed = subprocess.run(command, cwd=REPO, capture_output=True,
                               text=True, timeout=600)
    proof_dir = ROOT / "compatibility"
    command_log = proof_dir / (suffix + "-command.log")
    atomic_text(command_log, completed.stdout + "\n" + completed.stderr)
    if completed.returncode:
        raise RuntimeError("Compatibility failed for " + suffix + ": " +
                           completed.stderr[-1000:])
    receipt = output / "compatibility.json"
    analysis = output / "compatibility-analysis.log"
    negative = output / "negative-analysis.log"
    for source, destination in ((receipt, proof_dir / (suffix + "-compatibility.json")),
                                (analysis, proof_dir / (suffix + "-analysis.log")),
                                (negative, proof_dir / (suffix + "-negative.log"))):
        atomic_text(destination, source.read_text())
    return {"case_id": entry["case_id"], "command": " ".join(command),
            "exit_code": completed.returncode,
            "receipt": str((proof_dir / (suffix + "-compatibility.json")).relative_to(ROOT)),
            "receipt_sha256": sha(proof_dir / (suffix + "-compatibility.json")),
            "analysis_log": str((proof_dir / (suffix + "-analysis.log")).relative_to(ROOT)),
            "analysis_sha256": sha(proof_dir / (suffix + "-analysis.log")),
            "negative_log": str((proof_dir / (suffix + "-negative.log")).relative_to(ROOT)),
            "negative_sha256": sha(proof_dir / (suffix + "-negative.log"))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip", action="append", default=[])
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    args = parser.parse_args()
    if args.shards < 1 or not 0 <= args.shard < args.shards:
        raise ValueError("Invalid compatibility shard")
    manifest = json.loads(MANIFEST.read_text())
    index_path = ROOT / "compatibility" / "index.json"
    lock_path = REPO / ".runtime-work" / "c111271-compat-index.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    for number, entry in enumerate(manifest["cases"]):
        if number % args.shards != args.shard:
            continue
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        index = json.loads(index_path.read_text()) if index_path.is_file() else {
            "format": "worker-c111271-selected-compatibility-index-v1", "passed": []}
        passed = {row["case_id"]: row for row in index["passed"]}
        previous = passed.get(entry["case_id"])
        valid_previous = False
        if previous is not None:
            receipt_path = ROOT / previous["receipt"]
            if receipt_path.is_file():
                receipt = json.loads(receipt_path.read_text())
                command_parts = shlex.split(previous["command"])
                attempt = Path(command_parts[command_parts.index("--output") + 1])
                selection_path = attempt / "candidate-selection.json"
                selection = json.loads(selection_path.read_text()) if selection_path.is_file() else {}
                valid_previous = (receipt.get("passed") is True and
                    receipt.get("construction_sha256") == entry["construction_sha256"] and
                    receipt.get("runtime_manifest_sha256") == manifest["runtime_manifest_sha256"] and
                    selection.get("manifest_sha256") == sha(MANIFEST) and
                    selection.get("construction_sha256") == entry["construction_sha256"] and
                    sha(receipt_path) == previous["receipt_sha256"])
        if suffix in args.skip or valid_previous:
            continue
        row = run(entry)
        with lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            index = json.loads(index_path.read_text()) if index_path.is_file() else {
                "format": "worker-c111271-selected-compatibility-index-v1", "passed": []}
            passed = {saved["case_id"]: saved for saved in index["passed"]}
            passed[entry["case_id"]] = row
            index["passed"] = [passed[key] for key in sorted(passed)]
            atomic_text(index_path, json.dumps(index, indent=2))
            fcntl.flock(lock, fcntl.LOCK_UN)
        print(json.dumps({"case": suffix, "receipt_sha256": row["receipt_sha256"]}),
              flush=True)
    index = json.loads(index_path.read_text())
    passed = {row["case_id"]: row for row in index["passed"]}
    print(json.dumps({"compatibility_passed": len(passed),
                      "index_sha256": sha(index_path)}), flush=True)


if __name__ == "__main__":
    main()
