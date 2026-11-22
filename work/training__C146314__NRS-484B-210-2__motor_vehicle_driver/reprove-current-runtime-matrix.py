"""Reprove all selected right-pass candidates on the pinned CPU runtime."""
import concurrent.futures
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "current-runtime-reproof-manifest.json"
VALIDATOR = ROOT / ".runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def task(job):
    entry, candidate = job
    case = entry["case_id"]
    suffix = case.removeprefix(HERE.name + "__")
    selected = entry if candidate == "primary" else next(
        row for row in entry["candidates"] if row["id"] == candidate)
    manifest = MANIFEST if candidate == "primary" else HERE / f"current-runtime-{suffix}-{candidate}-diagnostic-manifest.json"
    output = ROOT / ".runtime-work/c146314-current-matrix" / suffix / candidate
    proof = HERE / "current-runtime-selected-proof" / suffix / candidate
    proof.mkdir(parents=True, exist_ok=True)
    attempt = output / "compat"
    saved_dir = output / "saved"
    common = ["--library", str(ROOT / "runtime/pipeline/library"), "--validator", str(VALIDATOR)]
    if not (attempt / "compatibility.json").is_file():
        command = [sys.executable, str(ROOT / "runtime.py"), "compatibility", "--manifest", str(manifest),
                   "--case", case, "--candidate", candidate, "--output", str(attempt), *common]
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        (proof / "compatibility.log").write_text(run.stdout + run.stderr)
        if run.returncode:
            raise ValueError(f"Compatibility failed {suffix}/{candidate}: {run.stdout[-500:]} {run.stderr[-500:]}")
    else:
        (proof / "compatibility.log").write_text((attempt / "compatibility.json").read_text())
    compat = json.loads((attempt / "compatibility.json").read_text())
    if not (compat.get("passed") is True and compat.get("case_id") == case and
            compat.get("candidate_id") == candidate and
            compat.get("construction_sha256") == selected["construction_sha256"] and
            compat.get("negative_removed") == "native-raw-actors.jsonl"):
        raise ValueError(f"Compatibility receipt differs {suffix}/{candidate}")
    if not (saved_dir / "v0001/processing.json").is_file():
        command = [sys.executable, str(ROOT / "runtime.py"), "process-saved", "--manifest", str(manifest),
                   "--case", case, "--attempt", str(attempt), "--output", str(saved_dir), *common]
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        (proof / "process-saved.log").write_text(run.stdout + run.stderr)
        if run.returncode:
            raise ValueError(f"Saved processing failed {suffix}/{candidate}: {run.stdout[-500:]} {run.stderr[-500:]}")
    else:
        (proof / "process-saved.log").write_text((saved_dir / "v0001/processing.json").read_text())
    saved = json.loads((saved_dir / "v0001/processing.json").read_text())
    if not (saved.get("passed") is True and saved.get("recorded_only") is True and
            saved.get("case_id") == case and saved.get("candidate_id") == candidate and
            saved.get("originals_preserved") is True and not saved.get("missing_evidence") and
            saved["timestamp_joins"]["passed"] is True and
            saved.get("physical_acceptance_claimed") is False and
            saved.get("legal_acceptance_claimed") is False):
        raise ValueError(f"Saved receipt differs {suffix}/{candidate}")
    for source, dest in ((attempt / "compatibility.json", "compatibility.json"),
                         (saved_dir / "v0001/processing.json", "saved-processing.json"),
                         (attempt / "compatibility-analysis.log", "analysis.log"),
                         (attempt / "negative-analysis.log", "negative-analysis.log")):
        (proof / dest).write_bytes(source.read_bytes())
    print(suffix, candidate, "compatibility and saved passed", flush=True)
    return {"case_id": case, "candidate_id": candidate,
            "construction_sha256": selected["construction_sha256"],
            "proof_dir": str(proof.relative_to(HERE)),
            "compatibility_sha256": sha(proof / "compatibility.json"),
            "saved_sha256": sha(proof / "saved-processing.json")}


def main():
    manifest = json.loads(MANIFEST.read_text())
    jobs = [(entry, candidate) for entry in manifest["cases"]
            for candidate in ("primary", "fallback1", "fallback2", "fallback3")]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(task, jobs))
    if len(rows) != 8:
        raise ValueError("Eight exact chains required")
    output = HERE / "current-runtime-matrix-progress.json"
    output.write_text(json.dumps({"format": "c146314-current-matrix-v1",
                                  "runtime_manifest_sha256": manifest["runtime_manifest_sha256"],
                                  "manifest_sha256": sha(MANIFEST), "completed": len(rows),
                                  "rows": rows, "original_native_accepted": False}, indent=2) + "\n")
    print(json.dumps({"chains": len(rows), "index_sha256": sha(output)}))


if __name__ == "__main__":
    main()
