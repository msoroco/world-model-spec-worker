"""Run the 16 long selected cases and 64 exact candidates through pinned offline checks."""
import concurrent.futures
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "current-runtime-reproof-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def task(job):
    entry, candidate = job
    case = entry["case_id"]
    suffix = case.removeprefix(HERE.name + "__")
    selected = entry if candidate == "primary" else next(
        item for item in entry["candidates"] if item["id"] == candidate)
    output = ROOT / ".runtime-work/c150142-current-long-offline-matrix" / suffix / candidate
    command = [sys.executable, str(ROOT / "runtime.py"), "offline", "--manifest", str(MANIFEST),
               "--case", case, "--candidate", candidate, "--output", str(output),
               "--python", sys.executable]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    log = HERE / "current-runtime-long-offline" / suffix / (candidate + ".log")
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(run.stdout + run.stderr)
    if run.returncode:
        raise ValueError(f"Offline failed {suffix}/{candidate}: {run.stdout[-350:]} {run.stderr[-350:]}")
    proof = json.loads(run.stdout)
    if not (proof.get("offline_passed") is True and proof.get("case_id") == case and
            proof.get("candidate_id") == candidate and proof.get("simulation_started") is False):
        raise ValueError("Wrong exact offline result: " + suffix + "/" + candidate)
    print(suffix, candidate, "passed", flush=True)
    return {"case_id": case, "candidate_id": candidate,
            "construction_sha256": selected["construction_sha256"],
            "log": str(log.relative_to(HERE)), "log_sha256": sha(log)}


def main():
    manifest = json.loads(MANIFEST.read_text())
    jobs = [(entry, candidate) for entry in manifest["cases"] if not entry.get("fixture_recipe")
            for candidate in ("primary", "fallback1", "fallback2", "fallback3")]
    if len(jobs) != 64:
        raise ValueError("Expected 16 long cases and 64 candidates")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(task, jobs))
    output = HERE / "current-runtime-long-offline-index.json"
    output.write_text(json.dumps({"format": "c150142-current-long-offline-v1",
                                  "manifest_sha256": sha(MANIFEST), "rows": rows,
                                  "original_native_observed": False}, indent=2) + "\n")
    print(json.dumps({"candidates": len(rows), "index_sha256": sha(output)}))


if __name__ == "__main__":
    main()
