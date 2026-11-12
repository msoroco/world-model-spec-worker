"""Pinned offline checks for all exact lateral-sweep candidate bundles."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "update052-extreme-right-sweep-manifest.json"
RUNS = ROOT / ".runtime-work/c110919-update052-lateral/offline-matrix"
PROOFS = HERE / "extreme_right_sweep_cases/lateral-receipts"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def task(entry, candidate, reference):
    ident = entry["case_id"]
    output = RUNS / sha(MANIFEST)[:12] / ident / candidate
    log = PROOFS / ident / candidate / "offline.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(ROOT / "runtime.py"), "offline",
               "--manifest", str(MANIFEST), "--case", ident,
               "--candidate", candidate, "--output", str(output),
               "--python", sys.executable]
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    log.write_text(result.stdout)
    if result.returncode:
        raise ValueError(f"Offline failed: {ident}/{candidate}: {result.stdout[-1000:]}")
    receipt = json.loads(result.stdout)
    if (receipt.get("case_id") != ident or receipt.get("candidate_id") != candidate or
            receipt.get("offline_passed") is not True or
            receipt.get("simulation_started") is not False):
        raise ValueError("Offline receipt differs")
    construction = HERE / reference["construction"]
    if sha(construction) != reference["construction_sha256"]:
        raise ValueError("Candidate construction changed")
    return {"case_id": ident, "candidate": candidate,
            "construction_sha256": sha(construction), "offline_log_sha256": sha(log)}


def main():
    manifest = json.loads(MANIFEST.read_text())
    entries = manifest["cases"]
    if len(entries) != 5:
        raise ValueError("Expected five exact timing cases")
    tasks = []
    for entry in entries:
        if [c["id"] for c in entry["candidates"]] != ["fallback1", "fallback2", "fallback3"]:
            raise ValueError("Exactly three fallbacks required")
        tasks.append((entry, "primary", entry))
        tasks.extend((entry, c["id"], c) for c in entry["candidates"])
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda args: task(*args), tasks))
    if len(results) != 20 or len({(x["case_id"], x["candidate"]) for x in results}) != 20:
        raise ValueError("Offline candidate matrix incomplete")
    proof = {"format": "c110919-extreme-right-sweep-offline-matrix-v1",
             "manifest_sha256": sha(MANIFEST),
             "candidate_stage_sha256": manifest["stage_sha256"],
             "results": results, "offline_passed": 20,
             "pinned_compatibility_passed": 0,
             "original_native_accepted": False, "canonical_selected": False}
    path = HERE / "update052-extreme-right-sweep-offline-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"offline_passed": 20, "proof_sha256": sha(path),
                      "compatibility_passed": 0, "selected": False}))


if __name__ == "__main__":
    main()
