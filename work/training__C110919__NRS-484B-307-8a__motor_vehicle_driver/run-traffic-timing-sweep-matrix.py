"""Pinned positive, negative and saved-processing proof for exact timing cases."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "update041-traffic-timing-sweep-manifest.json"
STAGE = HERE / "proposals/right-of-way-sweep-candidate.json"
LIBRARY = ROOT / "runtime/pipeline/library"
VALIDATOR = ROOT / ".runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck"
RUNS = ROOT / ".runtime-work/c110919-update047-timing-matrix"
LOGS = HERE / "traffic_timing_sweep_cases/timing-receipts"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, log):
    result = subprocess.run([sys.executable, str(ROOT / "runtime.py"), *args],
                            cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout)
    if result.returncode:
        raise ValueError(f"Timing matrix command failed at {log}: {result.stdout[-1300:]}")
    return json.loads(result.stdout)


def task(entry, name, ref):
    ident = entry["case_id"]
    run = RUNS / sha(MANIFEST)[:12] / ident / name
    log = LOGS / ident / name
    common = ["--manifest", str(MANIFEST), "--case", ident]
    args = [*common, "--candidate", name, "--library", str(LIBRARY),
            "--validator", str(VALIDATOR)]
    compatible = command(["compatibility", *args, "--output", str(run / "compatibility")],
                         log / "compatibility.log")
    if (compatible.get("passed") is not True or
            compatible.get("construction_sha256") != ref["construction_sha256"] or
            compatible.get("negative_removed") != "road_geometry.json" or
            compatible.get("case_id") != ident or compatible.get("candidate_id") != name):
        raise ValueError("Positive/negative compatibility receipt differs")
    saved = command(["process-saved", *common, "--library", str(LIBRARY),
                     "--validator", str(VALIDATOR), "--attempt", str(run / "compatibility"),
                     "--output", str(run / "saved")], log / "process-saved.log")
    if (saved.get("passed") is not True or saved.get("case_id") != ident or
            saved.get("candidate_id") != name or
            saved.get("originals_preserved") is not True or
            saved.get("timestamp_joins", {}).get("passed") is not True or
            saved.get("physical_acceptance_claimed") is not False or
            saved.get("legal_acceptance_claimed") is not False):
        raise ValueError("Saved timing processing receipt differs")
    proof = {"case_id": ident, "candidate_id": name,
             "construction_sha256": ref["construction_sha256"],
             "compatibility_receipt_sha256": sha(run / "compatibility/compatibility.json"),
             "saved_receipt_sha256": sha(run / "saved/v0001/processing.json"),
             "positive_negative_log_sha256": sha(log / "compatibility.log"),
             "saved_log_sha256": sha(log / "process-saved.log"),
             "original_native_accepted": False}
    print(json.dumps({"case": ident, "candidate": name, "passed": True}), flush=True)
    return proof


def main():
    manifest = json.loads(MANIFEST.read_text())
    offline = json.loads((HERE / "update041-traffic-timing-sweep-offline-proof.json").read_text())
    if (manifest.get("stage_sha256") != sha(STAGE) or
            offline.get("manifest_sha256") != sha(MANIFEST) or
            offline.get("offline_passed") != 20):
        raise ValueError("Exact stage, manifest or offline proof changed")
    tasks = []
    for entry in manifest["cases"]:
        tasks.append((entry, "primary", entry))
        tasks.extend((entry, candidate["id"], candidate) for candidate in entry["candidates"])
    if len(tasks) != 20:
        raise ValueError("Expected twenty exact timing bundles")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda args: task(*args), tasks))
    index = {"format": "c110919-timing-sweep-pinned-matrix-v1",
             "manifest_sha256": sha(MANIFEST), "stage_sha256": sha(STAGE),
             "offline_proof_sha256": sha(HERE / "update041-traffic-timing-sweep-offline-proof.json"),
             "candidate_count": len(results), "results": results,
             "canonical_selected": False, "original_native_accepted": False}
    path = HERE / "update047-traffic-timing-sweep-matrix-index.json"
    path.write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"candidates": len(results), "index_sha256": sha(path),
                      "canonical_selected": False}))


if __name__ == "__main__":
    main()
