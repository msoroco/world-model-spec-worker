"""Run all staged railroad-reference candidates under the current selected manifest."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from camera_lifecycle_audit import audit as source_camera_audit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "selected-rail-reference-manifest.json"
CASE = HERE.name + "__rail_reference"
LIBRARY = ROOT / "runtime/pipeline/library"
VALIDATOR = ROOT / ".runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck"
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, log):
    process = subprocess.run([sys.executable, str(ROOT / "runtime.py"), *args],
                             cwd=ROOT, text=True, capture_output=True)
    log.write_text(process.stdout + process.stderr)
    if process.returncode:
        raise ValueError(f"Staged rail candidate command failed: {log}")
    return json.loads(process.stdout)


def paths(candidate):
    stem = f"c110454-update018-selected-rail-{candidate}"
    return (ROOT / ".runtime-work" / (stem + "-offline-v2"),
            ROOT / ".runtime-work" / (stem + "-compatibility"),
            ROOT / ".runtime-work" / (stem + "-saved"))


def main():
    manifest = json.loads(MANIFEST.read_text())
    entry = manifest["cases"][0]
    assert entry["case_id"] == CASE and entry["kind"] == "delivery"
    assert VALIDATOR.is_file()
    results = []
    for candidate in CANDIDATES:
        offline, attempt, saved_dir = paths(candidate)
        prefix = "update018-selected-rail-" + candidate
        if candidate == "primary":
            logs = [HERE / "update018-selected-rail-offline.log",
                    HERE / "update018-selected-rail-compatibility.log",
                    HERE / "update018-selected-rail-saved.log"]
        else:
            logs = [HERE / (prefix + "-" + phase + ".log")
                    for phase in ("offline", "compatibility", "saved")]
            if not all(log.is_file() for log in logs):
                if any(log.exists() for log in logs) or any(
                        path.exists() for path in (offline, attempt, saved_dir)):
                    raise ValueError("Incomplete prior candidate; retain it and use fresh output names")
                common = ["--manifest", str(MANIFEST), "--case", CASE]
                run(["offline", *common, "--candidate", candidate,
                     "--output", str(offline), "--python", sys.executable], logs[0])
                run(["compatibility", *common, "--candidate", candidate,
                     "--output", str(attempt), "--library", str(LIBRARY),
                     "--validator", str(VALIDATOR)], logs[1])
                run(["process-saved", *common, "--attempt", str(attempt),
                     "--output", str(saved_dir), "--library", str(LIBRARY),
                     "--validator", str(VALIDATOR)], logs[2])
        offline_receipt, compat_receipt, saved_receipt = (
            json.loads(log.read_text()) for log in logs)
        selected = entry if candidate == "primary" else next(
            item for item in entry["candidates"] if item["id"] == candidate)
        assert sha(HERE / selected["construction"]) == selected["construction_sha256"]
        assert (offline_receipt["offline_passed"] is True and
                offline_receipt["candidate_id"] == candidate)
        assert (compat_receipt["passed"] is True and
                compat_receipt["candidate_id"] == candidate and
                compat_receipt["construction_sha256"] == selected["construction_sha256"] and
                compat_receipt["negative_removed"] == "statutory_context.json")
        assert (saved_receipt["passed"] is True and
                saved_receipt["candidate_id"] == candidate and
                saved_receipt["originals_preserved"] is True and
                saved_receipt["physical_acceptance_claimed"] is False and
                saved_receipt["legal_acceptance_claimed"] is False)
        assert (attempt / "candidate-selection.json").is_file()
        selection = json.loads((attempt / "candidate-selection.json").read_text())
        assert selection["manifest_sha256"] == sha(MANIFEST)
        source_review = source_camera_audit(
            attempt, logs[2], CASE, candidate, selected["construction_sha256"],
            diagnostic=True)
        assert (source_review["camera_source_shape_passed"] is True and
                source_review["passed"] is False)
        results.append({"candidate_id": candidate,
                        "construction_sha256": selected["construction_sha256"],
                        "offline_log_sha256": sha(logs[0]),
                        "compatibility_log_sha256": sha(logs[1]),
                        "saved_processing_log_sha256": sha(logs[2]),
                        "selected_manifest_sha256": sha(MANIFEST),
                        "source_and_camera_shape_passed": True,
                        "simulation_started": False,
                        "physical_or_legal_acceptance_claimed": False})
        print(json.dumps({"candidate": candidate, "passed": True}), flush=True)
    proof = {"format": "c110454-selected-rail-reference-cpu-matrix-v1",
             "case_id": CASE, "candidate_count": 4, "candidates": results,
             "selection_stage_only": True, "canonical_assignment_ready": False}
    output = HERE / "update018-selected-rail-matrix.json"
    output.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"candidate_count": 4, "proof_sha256": sha(output)}))


if __name__ == "__main__":
    main()
