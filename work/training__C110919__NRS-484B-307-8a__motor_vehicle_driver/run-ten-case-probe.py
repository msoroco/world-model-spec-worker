"""Pinned offline, source-negative compatibility and saved proof for 40 bundles."""
import concurrent.futures
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "update038-ten-case-probe-manifest.json"
LIBRARY = ROOT / "runtime/pipeline/library"
VALIDATOR = ROOT / ".runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck"
RUN_ROOT = ROOT / ".runtime-work/c110919-update038-ten-case-matrix"
PROOFS = HERE / "update038-ten-case-proofs"
ORDER = ("reference", "contrast", "absent_reference", "absent_reference_contrast",
         "green_release_wait", "green_release_red_turn", "yield_wait",
         "yield_conflict_entry", "traffic_yield_wait",
         "traffic_conflict_entry")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, log):
    run = subprocess.run([sys.executable, str(ROOT / "runtime.py"), *args], cwd=ROOT,
                         text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         check=False)
    log.write_text(run.stdout)
    if run.returncode:
        raise ValueError("Ten-case CPU command failed: " + str(log) + " " + run.stdout[-1800:])
    return json.loads(run.stdout)


def task(entry, candidate_id, candidate):
    suffix = entry["case_id"].removeprefix(HERE.name + "__")
    case_id = entry["case_id"]
    folder = PROOFS / suffix / candidate_id
    folder.mkdir(parents=True, exist_ok=True)
    run = RUN_ROOT / sha(MANIFEST)[:12] / suffix / candidate_id
    common = ["--manifest", str(MANIFEST), "--case", case_id]
    offline = command(["offline", *common, "--candidate", candidate_id,
                       "--output", str(run / "offline"), "--python", sys.executable],
                      folder / "offline.log")
    if offline.get("offline_passed") is not True:
        raise ValueError("Exact offline candidate did not pass: " + suffix + " " + candidate_id)
    args = [*common, "--candidate", candidate_id, "--library", str(LIBRARY),
            "--validator", str(VALIDATOR)]
    compat = command(["compatibility", *args, "--output", str(run / "compatibility")],
                     folder / "compatibility.log")
    if not (compat["passed"] is True and compat["case_id"] == case_id and
            compat["candidate_id"] == candidate_id and
            compat["construction_sha256"] == candidate["construction_sha256"] and
            compat["negative_removed"] == "road_geometry.json"):
        raise ValueError("Exact compatibility or missing-road negative differs")
    saved = command(["process-saved", *common, "--library", str(LIBRARY),
                     "--validator", str(VALIDATOR), "--attempt", str(run / "compatibility"),
                     "--output", str(run / "saved")], folder / "process-saved.log")
    if not (saved["passed"] is True and saved["case_id"] == case_id and
            saved["candidate_id"] == candidate_id and
            saved["originals_preserved"] is True and saved["missing_evidence"] is False and
            saved["timestamp_joins"]["passed"] is True and
            saved["physical_acceptance_claimed"] is False and
            saved["legal_acceptance_claimed"] is False):
        raise ValueError("Exact saved-processing receipt differs")
    proof = {"format": "c110919-ten-case-candidate-cpu-probe-v1",
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
    if ([row["case_id"].removeprefix(HERE.name + "__") for row in entries] != list(ORDER) or
            any(row["kind"] != "delivery" or row["id"] != "primary" or
                [item["id"] for item in row["candidates"]] !=
                ["fallback1", "fallback2", "fallback3"] for row in entries)):
        raise ValueError("Ten-case probe inventory changed")
    tasks = [(entry, "primary", entry) for entry in entries]
    tasks += [(entry, candidate["id"], candidate) for entry in entries
              for candidate in entry["candidates"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(task, *args) for args in tasks]
        results = [future.result() for future in futures]
    if len(results) != 40 or len({(row["case_id"], row["candidate_id"]) for row in results}) != 40:
        raise ValueError("Ten-case candidate matrix incomplete")
    index = {"format": "c110919-ten-case-cpu-probe-matrix-v1",
             "manifest_sha256": sha(MANIFEST), "cases": 10, "candidates": 40,
             "results": results, "canonical_selected": False,
             "original_native_accepted": False}
    path = HERE / "update038-ten-case-matrix-index.json"
    path.write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"cases": 10, "candidates": 40,
                      "index_sha256": sha(path), "canonical_selected": False}))


if __name__ == "__main__":
    main()
