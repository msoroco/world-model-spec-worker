"""Pinned offline, compatibility and saved path for both green-release cases."""
import concurrent.futures
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "draft-green-release-execution-manifest.json"
LIBRARY = ROOT / "runtime/pipeline/library"
VALIDATOR = ROOT / ".runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck"
RUN_ROOT = ROOT / ".runtime-work/c110919-update027-green-matrix"
PROOFS = HERE / "update027-green-matrix-proofs"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, log):
    run = subprocess.run([sys.executable, str(ROOT / "runtime.py"), *args], cwd=ROOT,
                         text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    log.write_text(run.stdout)
    if run.returncode:
        raise ValueError("Green-release CPU command failed: " + str(log) + " " + run.stdout[-2000:])
    return json.loads(run.stdout)


def task(entry, candidate_id, candidate):
    suffix = entry["case_id"].removeprefix(HERE.name + "__")
    case_id = entry["case_id"]
    folder = PROOFS / suffix / candidate_id
    folder.mkdir(parents=True, exist_ok=True)
    run = RUN_ROOT / suffix / candidate_id
    common = ["--manifest", str(MANIFEST), "--case", case_id]
    offline = command(["offline", *common, "--candidate", candidate_id,
                       "--output", str(run / "offline"), "--python", sys.executable],
                      folder / "offline.log")
    if offline.get("offline_passed") is not True:
        raise ValueError("Offline candidate did not pass")
    args = [*common, "--candidate", candidate_id, "--library", str(LIBRARY),
            "--validator", str(VALIDATOR)]
    compatibility = command(["compatibility", *args, "--output", str(run / "compatibility")],
                            folder / "compatibility.log")
    if compatibility.get("passed") is not True or compatibility.get("case_id") != case_id or \
       compatibility.get("candidate_id") != candidate_id or \
       compatibility.get("construction_sha256") != candidate["construction_sha256"] or \
       compatibility.get("negative_removed") != "road_geometry.json":
        raise ValueError("Green-release compatibility or missing-source negative differs")
    saved = command(["process-saved", *common, "--library", str(LIBRARY),
                     "--validator", str(VALIDATOR), "--attempt", str(run / "compatibility"),
                     "--output", str(run / "saved")], folder / "process-saved.log")
    if saved.get("passed") is not True or saved.get("case_id") != case_id or \
       saved.get("candidate_id") != candidate_id or saved.get("originals_preserved") is not True or \
       saved.get("missing_evidence") is not False or \
       saved.get("physical_acceptance_claimed") is not False or \
       saved.get("legal_acceptance_claimed") is not False:
        raise ValueError("Green-release saved-processing identity or source preservation differs")
    proof = {"format": "c110919-green-release-candidate-cpu-v1",
             "case_id": case_id, "candidate_id": candidate_id,
             "manifest_sha256": sha(MANIFEST),
             "construction_sha256": candidate["construction_sha256"],
             "offline_log_sha256": sha(folder / "offline.log"),
             "compatibility_log_sha256": sha(folder / "compatibility.log"),
             "process_saved_log_sha256": sha(folder / "process-saved.log"),
             "compatibility_receipt_sha256": sha(run / "compatibility/compatibility.json"),
             "saved_receipt_sha256": sha(run / "saved/v0001/processing.json"),
             "original_native_accepted": False}
    path = folder / "proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"case": suffix, "candidate": candidate_id, "passed": True}), flush=True)
    return {"case_id": case_id, "candidate_id": candidate_id,
            "proof": str(path.relative_to(HERE)), "sha256": sha(path)}


def main():
    manifest = json.loads(MANIFEST.read_text())
    entries = manifest["cases"]
    if len(entries) != 2 or any(entry["kind"] != "draft_not_selected" or
                                len(entry["candidates"]) != 3 for entry in entries):
        raise ValueError("Green-release draft pair changed")
    tasks = [(entry, "primary", entry) for entry in entries]
    tasks += [(entry, candidate["id"], candidate) for entry in entries
              for candidate in entry["candidates"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(task, *args) for args in tasks]
        results = [future.result() for future in futures]
    if len(results) != 8:
        raise ValueError("Green-release candidate matrix incomplete")
    index = {"format": "c110919-green-release-cpu-matrix-v1",
             "manifest_sha256": sha(MANIFEST), "cases": 2, "candidates": 8,
             "results": results, "canonical_selected": False,
             "original_native_accepted": False}
    path = HERE / "update027-green-matrix-index.json"
    path.write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"cases": 2, "candidates": 8, "index_sha256": sha(path)}))


if __name__ == "__main__":
    main()
