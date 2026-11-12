"""Pinned offline, diagnostic compatibility and saved checks for eight yield bundles."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "draft-yield-branch-execution-manifest.json"
LIBRARY = ROOT / "runtime/pipeline/library"
VALIDATOR = ROOT / ".runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck"
RUNS = ROOT / ".runtime-work/c110919-update034-yield-full-matrix"
PROOFS = HERE / "yield_branch_cases/receipts"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, log):
    completed = subprocess.run([sys.executable, str(ROOT / "runtime.py"), *args],
                               cwd=ROOT, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, check=False)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(completed.stdout)
    if completed.returncode:
        raise ValueError(f"Yield CPU command failed: {log}: {completed.stdout[-1600:]}")
    return json.loads(completed.stdout)


def task(entry, candidate, reference):
    suffix = entry["case_id"].removeprefix(HERE.name + "__")
    folder = PROOFS / suffix / candidate
    folder.mkdir(parents=True, exist_ok=True)
    run = RUNS / suffix / candidate
    common = ["--manifest", str(MANIFEST), "--case", entry["case_id"]]
    offline = command(["offline", *common, "--candidate", candidate,
                       "--output", str(run / "offline"), "--python", sys.executable],
                      folder / "offline.log")
    if offline.get("offline_passed") is not True or offline.get("simulation_started") is not False:
        raise ValueError("Offline construction failed")
    args = [*common, "--candidate", candidate, "--library", str(LIBRARY),
            "--validator", str(VALIDATOR)]
    compat = command(["compatibility", *args, "--output", str(run / "compatibility")],
                     folder / "compatibility.log")
    if not (compat["passed"] is True and compat["case_id"] == entry["case_id"] and
            compat["candidate_id"] == candidate and
            compat["construction_sha256"] == reference["construction_sha256"] and
            compat["negative_removed"] == "road_geometry.json"):
        raise ValueError("Exact compatibility or missing-road negative differs")
    saved = command(["process-saved", *common, "--library", str(LIBRARY),
                     "--validator", str(VALIDATOR),
                     "--attempt", str(run / "compatibility"),
                     "--output", str(run / "saved")],
                    folder / "process-saved.log")
    if not (saved["passed"] is True and saved["case_id"] == entry["case_id"] and
            saved["candidate_id"] == candidate and
            saved["originals_preserved"] is True and
            saved["timestamp_joins"]["passed"] is True and
            saved["physical_acceptance_claimed"] is False and
            saved["legal_acceptance_claimed"] is False):
        raise ValueError("Exact saved processing receipt differs")
    proof = {"format": "c110919-yield-candidate-cpu-probe-v1",
             "case_id": entry["case_id"], "candidate_id": candidate,
             "manifest_sha256": sha(MANIFEST),
             "construction_sha256": reference["construction_sha256"],
             "offline_log_sha256": sha(folder / "offline.log"),
             "compatibility_log_sha256": sha(folder / "compatibility.log"),
             "process_saved_log_sha256": sha(folder / "process-saved.log"),
             "compatibility_receipt_sha256": sha(run / "compatibility/compatibility.json"),
             "saved_receipt_sha256": sha(run / "saved/v0001/processing.json"),
             "original_native_accepted": False}
    path = folder / "proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"case": suffix, "candidate": candidate, "passed": True}), flush=True)
    return {"case_id": entry["case_id"], "candidate_id": candidate,
            "proof": str(path.relative_to(HERE)), "sha256": sha(path)}


def main():
    manifest = json.loads(MANIFEST.read_text())
    entries = manifest["cases"]
    if ([row["case_id"].removeprefix(HERE.name + "__") for row in entries] !=
            ["yield_wait", "yield_conflict_entry"] or
            any(row["kind"] != "draft_not_selected" or
                [item["id"] for item in row["candidates"]] !=
                ["fallback1", "fallback2", "fallback3"] for row in entries)):
        raise ValueError("Exact draft yield inventory changed")
    tasks = [(entry, "primary", entry) for entry in entries]
    tasks += [(entry, item["id"], item) for entry in entries
              for item in entry["candidates"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(task, *item) for item in tasks]
        results = [future.result() for future in futures]
    if len(results) != 8 or len({(row["case_id"], row["candidate_id"])
                                for row in results}) != 8:
        raise ValueError("Yield candidate matrix incomplete")
    index = {"format": "c110919-yield-cpu-probe-matrix-v1",
             "manifest_sha256": sha(MANIFEST), "cases": 2, "candidates": 8,
             "results": results, "canonical_selected": False,
             "original_native_accepted": False}
    path = HERE / "yield_branch_cases/matrix-index.json"
    path.write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"cases": 2, "candidates": 8, "index_sha256": sha(path),
                      "canonical_selected": False}))


if __name__ == "__main__":
    main()
