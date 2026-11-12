"""Prove all qualified timing and lateral bundles through pinned CPU paths."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "update057-qualified-sweep-manifest.json"
RUNS = ROOT / ".runtime-work/c110919-update057-qualified-matrix"
LOGS = HERE / "qualified_sweep_cases/receipts"
LIBRARY = ROOT / "runtime/pipeline/library"
VALIDATOR = ROOT / ".runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, log):
    result = subprocess.run([sys.executable, str(ROOT / "runtime.py"), *args],
                            cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout)
    if result.returncode:
        raise ValueError(f"CPU proof failed at {log}: {result.stdout[-1200:]}")
    return json.loads(result.stdout)


def task(entry, name, ref):
    cid = entry["case_id"]
    folder = RUNS / sha(MANIFEST)[:12] / cid / name
    logs = LOGS / cid / name
    common = ["--manifest", str(MANIFEST), "--case", cid]
    off = run(["offline", *common, "--candidate", name,
               "--output", str(folder / "offline"), "--python", sys.executable],
              logs / "offline.log")
    if off.get("offline_passed") is not True or off.get("simulation_started") is not False:
        raise ValueError("Offline construction proof differs")
    compatible = run(["compatibility", *common, "--candidate", name,
                      "--library", str(LIBRARY), "--validator", str(VALIDATOR),
                      "--output", str(folder / "compatibility")],
                     logs / "compatibility.log")
    if (compatible.get("passed") is not True or
            compatible.get("negative_removed") != "road_geometry.json" or
            compatible.get("construction_sha256") != ref["construction_sha256"] or
            compatible.get("case_id") != cid or compatible.get("candidate_id") != name):
        raise ValueError("Positive/negative compatibility receipt differs")
    saved = run(["process-saved", *common, "--library", str(LIBRARY),
                 "--validator", str(VALIDATOR),
                 "--attempt", str(folder / "compatibility"),
                 "--output", str(folder / "saved")], logs / "process-saved.log")
    if (saved.get("passed") is not True or saved.get("case_id") != cid or
            saved.get("candidate_id") != name or
            saved.get("originals_preserved") is not True or
            saved.get("timestamp_joins", {}).get("passed") is not True or
            saved.get("physical_acceptance_claimed") is not False or
            saved.get("legal_acceptance_claimed") is not False):
        raise ValueError("Saved processing receipt differs")
    print(json.dumps({"case": cid, "candidate": name, "passed": True}), flush=True)
    return {"case_id": cid, "candidate_id": name,
            "construction_sha256": ref["construction_sha256"],
            "offline_log_sha256": sha(logs / "offline.log"),
            "compatibility_receipt_sha256": sha(folder / "compatibility/compatibility.json"),
            "compatibility_log_sha256": sha(logs / "compatibility.log"),
            "saved_receipt_sha256": sha(folder / "saved/v0001/processing.json"),
            "saved_log_sha256": sha(logs / "process-saved.log"),
            "original_native_accepted": False}


def main():
    manifest = json.loads(MANIFEST.read_text())
    if (len(manifest["cases"]) != 10 or
            manifest["stage_sha256"] != sha(HERE / "proposals/cases.json")):
        raise ValueError("Qualified manifest or canonical stage changed")
    jobs = []
    for entry in manifest["cases"]:
        if [c["id"] for c in entry["candidates"]] != ["fallback1", "fallback2", "fallback3"]:
            raise ValueError("Exactly three distinct fallbacks required")
        jobs.append((entry, "primary", entry))
        jobs.extend((entry, c["id"], c) for c in entry["candidates"])
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda job: task(*job), jobs))
    index = {"format": "c110919-qualified-sweep-pinned-matrix-v1",
             "manifest_sha256": sha(MANIFEST),
             "stage_sha256": manifest["stage_sha256"],
             "candidate_count": len(results), "results": results,
             "original_native_accepted": False}
    target = HERE / "update057-qualified-sweep-matrix-index.json"
    target.write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"candidate_count": len(results), "index_sha256": sha(target)}))


if __name__ == "__main__":
    main()
