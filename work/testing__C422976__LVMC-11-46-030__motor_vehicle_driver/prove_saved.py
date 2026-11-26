"""Run exact-case saved processing against current diagnostic compatibility attempts."""

import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess

from school_lane_controls import VARIANTS


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c422976-owner"
ASSIGNMENT = HERE.name
VALIDATOR = REPO / ".runtime-work/c227824-owner/decoder/.lake/build/bin/adapterCheck"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_attempt(case_id, suffix):
    sealed = digest(HERE / "cases" / suffix / "compatibility.json")
    for path in SCRATCH.glob("compat-*/compatibility.json"):
        if digest(path) == sealed and json.loads(path.read_text()).get("case_id") == case_id:
            return path.parent
    raise ValueError("matching current exact compatibility attempt missing: " + suffix)


def one(variant):
    suffix = variant.suffix
    case_id = ASSIGNMENT + "__" + suffix
    attempt = source_attempt(case_id, suffix)
    output = SCRATCH / ("saved-" + suffix)
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH), TMPDIR=str(SCRATCH),
               MPLCONFIGDIR=str(SCRATCH / "mpl"), PYTHONDONTWRITEBYTECODE="1",
               OMP_NUM_THREADS="1")
    command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
               "process-saved", "--manifest", str(HERE / "diagnostic-execution-manifest.json"),
               "--case", case_id, "--attempt", str(attempt), "--output", str(output),
               "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
    result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
    if result.returncode:
        (SCRATCH / ("saved-error-" + suffix + ".log")).write_text(result.stdout + result.stderr)
        return {"case_id": case_id, "exit_code": result.returncode,
                "error": (result.stdout + result.stderr)[-1500:]}
    receipt = json.loads(result.stdout)
    if (receipt.get("passed") is not True or receipt.get("recorded_only") is not True or
            receipt.get("originals_preserved") is not True or
            receipt.get("timestamp_joins", {}).get("frames") != 900 or
            receipt.get("physical_acceptance_claimed") is not False):
        raise ValueError("saved-only receipt incomplete: " + suffix)
    folder = HERE / "cases" / suffix
    log = folder / "cpu-saved.log"
    log.write_text(json.dumps({"case_id": case_id, "passed": True, "recorded_only": True,
                               "originals_preserved": True, "timestamp_joins": 900,
                               "physical_acceptance_claimed": False}, sort_keys=True) + "\n")
    return {"case_id": case_id, "exit_code": 0, "command": " ".join(command),
            "log": str(log.relative_to(HERE)), "log_sha256": digest(log),
            "attempt": str(attempt), "saved_output": str(output)}


def main():
    if not VALIDATOR.is_file():
        raise ValueError("pinned compiled CPU validator missing")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(one, VARIANTS))
    (HERE / "saved-proof-summary.json").write_text(
        json.dumps({"format": "c422976-saved-proof-summary-v1", "cases": results},
                   indent=2, sort_keys=True) + "\n")
    for item in results:
        print(item["case_id"].rsplit("__", 1)[-1], item["exit_code"])
    if any(item["exit_code"] for item in results):
        raise ValueError("selected saved processing failed")


if __name__ == "__main__":
    main()
