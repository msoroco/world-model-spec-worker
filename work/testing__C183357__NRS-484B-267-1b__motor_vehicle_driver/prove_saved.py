"""Run exact saved-only positive and missing-original-source CPU proofs."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from native_packet import AID

HERE = Path(__file__).resolve().parent
CASES = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))["cases"]
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c183357-1b"
MANIFEST = HERE / "execution-manifest.json"
VALIDATOR = ROOT / ".runtime-work/c233829/decoder/.lake/build/bin/adapterCheck"
HISTORY = "original-curb-position-history.jsonl"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "output-root"),
               TMPDIR=str(SCRATCH / "tmp"))
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=1200)
    if completed.returncode:
        raise RuntimeError(completed.stderr[-1800:])
    return json.loads(completed.stdout)


def one(case):
    name, case_id = case["variant"], AID + "__" + case["variant"]
    attempt = SCRATCH / ("compat-" + name + "-v4")
    selection = attempt / "candidate-selection.json"
    if selection.exists():
        selection.unlink()
    output = SCRATCH / ("saved-" + name + "-v1")
    command = [sys.executable, str(ROOT / "runtime.py"), "process-saved",
               "--manifest", str(MANIFEST), "--case", case_id,
               "--attempt", str(attempt), "--output", str(output),
               "--library", str(ROOT / "runtime/library"), "--validator", str(VALIDATOR)]
    positive = run(command)
    if not (positive.get("passed") and positive.get("originals_preserved") and
            positive.get("timestamp_joins", {}).get("passed") and not positive.get("missing_evidence")):
        raise ValueError("saved-only positive proof incomplete: " + name)
    log = HERE / ("cpu-saved-" + name + ".log")
    log.write_text(json.dumps(positive, sort_keys=True) + "\n", encoding="utf-8")
    missing = SCRATCH / ("saved-missing-attempt-" + name + "-v1")
    if not missing.exists():
        shutil.copytree(attempt, missing, copy_function=os.link)
        (missing / HISTORY).unlink()
    negative_output = SCRATCH / ("saved-missing-" + name + "-v1")
    negative_command = command.copy()
    negative_command[negative_command.index("--attempt") + 1] = str(missing)
    negative_command[negative_command.index("--output") + 1] = str(negative_output)
    negative = run(negative_command)
    if not negative.get("missing_evidence"):
        raise ValueError("missing original history not rejected: " + name)
    feedback = negative_output / "v0001/feedback.json"
    if HISTORY not in feedback.read_text(encoding="utf-8"):
        raise ValueError("negative feedback did not identify missing history: " + name)
    negative_log = HERE / ("cpu-saved-" + name + "-missing.log")
    negative_log.write_text(json.dumps(negative, sort_keys=True) + "\n", encoding="utf-8")
    return case_id, {"command": " ".join(command), "feedback_command": " ".join(negative_command),
                     "test_log": log.name, "test_log_sha256": sha(log), "test_exit_code": 0,
                     "feedback_log": negative_log.name, "feedback_log_sha256": sha(negative_log),
                     "feedback_test_exit_code": 0, "recorded_only": True,
                     "diagnostic_fixture": True, "physical_acceptance_claimed": False}


def main():
    outcomes = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(one, case) for case in CASES]
        for future in as_completed(futures):
            case_id, proof = future.result()
            outcomes[case_id] = proof
            print(case_id.removeprefix(AID + "__") + ": saved-only passed", flush=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for entry in manifest["cases"]:
        entry["post_capture"] = outcomes[entry["case_id"]]
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
