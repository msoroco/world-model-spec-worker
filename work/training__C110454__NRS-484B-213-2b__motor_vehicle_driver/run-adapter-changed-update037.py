"""Rebind seven selected cases and 28 candidates after package receipt binding."""
import concurrent.futures
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from camera_lifecycle_audit import audit as camera_audit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "update037-adapter-probe-manifest.json"
LIBRARY = ROOT / "runtime/pipeline/library"
VALIDATOR = ROOT / ".runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck"
RUN_ROOT = ROOT / ".runtime-work/c110454-update037-adapter-probe"
PROOF_ROOT = HERE / "update037-adapter-proofs"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def execute(args, log):
    process = subprocess.run([sys.executable, str(ROOT / "runtime.py"), *args],
                             cwd=ROOT, capture_output=True, text=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(process.stdout + process.stderr)
    require(process.returncode == 0, f"Current selected proof command failed: {log}")
    return json.loads(process.stdout)


def phase(args, output, log):
    if log.is_file():
        require(output.is_dir(), f"Retained proof output missing: {output}")
        return json.loads(log.read_text())
    require(not output.exists(), f"Incomplete retained proof output: {output}")
    return execute(args, log)


def candidate_task(entry, candidate):
    case = entry["case_id"]
    suffix = case.rsplit("__", 1)[-1]
    ident = candidate.get("id", "primary")
    target = RUN_ROOT / suffix / ident
    proof_dir = PROOF_ROOT / suffix / ident
    offline, attempt, saved_dir = (target / phase_name for phase_name in
                                   ("offline", "compatibility", "saved"))
    offline_log, compat_log, saved_log = (proof_dir / name for name in
                                          ("offline.log", "compatibility.log",
                                           "process-saved.log"))
    common = ["--manifest", str(MANIFEST), "--case", case]
    offline_receipt = phase(["offline", *common, "--candidate", ident,
                             "--output", str(offline), "--python", sys.executable],
                            offline, offline_log)
    require(offline_receipt.get("offline_passed") is True and
            offline_receipt.get("candidate_id") == ident,
            f"Selected offline receipt differs: {case}/{ident}")
    compat_receipt = phase(["compatibility", *common, "--candidate", ident,
                            "--output", str(attempt), "--library", str(LIBRARY),
                            "--validator", str(VALIDATOR)], attempt, compat_log)
    required = "statutory_context.json" if suffix.startswith(("rail_", "oneway_")) else "native_samples.jsonl"
    if suffix.startswith("traversal_"):
        required = "native_samples.jsonl"
    require(compat_receipt.get("passed") is True and
            compat_receipt.get("candidate_id") == ident and
            compat_receipt.get("construction_sha256") == candidate["construction_sha256"] and
            compat_receipt.get("negative_removed") == required,
            f"Selected compatibility receipt differs: {case}/{ident}")
    saved = phase(["process-saved", *common, "--attempt", str(attempt),
                   "--output", str(saved_dir), "--library", str(LIBRARY),
                   "--validator", str(VALIDATOR)], saved_dir, saved_log)
    require(saved.get("passed") is True and saved.get("recorded_only") is True and
            saved.get("originals_preserved") is True and
            saved.get("missing_evidence") is False and
            saved.get("physical_acceptance_claimed") is False and
            saved.get("legal_acceptance_claimed") is False and
            saved.get("candidate_id") == ident,
            f"Selected saved-processing receipt differs: {case}/{ident}")
    selection = json.loads((attempt / "candidate-selection.json").read_text())
    require(selection.get("manifest_sha256") == sha(MANIFEST) and
            selection.get("construction_sha256") == candidate["construction_sha256"],
            f"Selected manifest binding differs: {case}/{ident}")
    source = camera_audit(attempt, saved_log, case, ident,
                          candidate["construction_sha256"], diagnostic=True)
    require(source["camera_source_shape_passed"] and not source["passed"],
            f"Selected source/camera proof differs: {case}/{ident}")
    proof = {"case_id": case, "candidate_id": ident,
             "manifest_sha256": sha(MANIFEST),
             "construction_sha256": candidate["construction_sha256"],
             "offline_log_sha256": sha(offline_log),
             "compatibility_log_sha256": sha(compat_log),
             "process_saved_log_sha256": sha(saved_log),
             "source_and_camera_shape_passed": True,
             "synthetic_diagnostic": True, "physical_acceptance_claimed": False}
    proof_dir.mkdir(parents=True, exist_ok=True)
    proof_path = proof_dir / "proof.json"
    proof_path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"case": suffix, "candidate": ident, "passed": True}), flush=True)
    return {"case_id": case, "candidate_id": ident,
            "proof": str(proof_path.relative_to(HERE)), "sha256": sha(proof_path)}


def main():
    manifest = json.loads(MANIFEST.read_text())
    entries = manifest["cases"]
    require(len(entries) == 7 and all(entry["kind"] == "delivery" and
                                  len(entry["candidates"]) == 3 for entry in entries),
            "Seven selected delivery cases and three fallbacks required")
    require(VALIDATOR.is_file(), "Pinned validator missing")
    tasks = [(entry, candidate) for entry in entries if not entry["case_id"].endswith(("__traversal_reference", "__traversal_contrast"))
             for candidate in (entry, *entry["candidates"])]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(candidate_task, entry, candidate)
                   for entry, candidate in tasks]
        results = [future.result() for future in futures]
    require(len(results) == 20, "Selected candidate matrix incomplete")
    index = {"format": "c110454-adapter-changed-cpu-matrix-v1",
             "manifest_sha256": sha(MANIFEST), "case_count": 7,
             "candidate_count": 20, "results": results,
             "original_native_or_delivery_acceptance_claimed": False}
    output = HERE / "update037-adapter-changed-index.json"
    output.write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"case_count": 7, "candidate_count": 20,
                      "index_sha256": sha(output)}))


if __name__ == "__main__":
    main()
