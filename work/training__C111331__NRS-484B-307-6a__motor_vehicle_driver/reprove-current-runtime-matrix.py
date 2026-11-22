"""Reprove selected speed compatibility and recorded-only saved processing."""
import concurrent.futures
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "current-runtime-reproof-manifest.json"
LIBRARY = ROOT / "runtime/pipeline/library"
VALIDATOR = ROOT / ".runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError(f"CPU proof failed: {log}: {result.stdout[-1000:]} {result.stderr[-1000:]}")
    return json.loads(result.stdout)


def task(entry, candidate):
    case = entry["case_id"]
    suffix = case.removeprefix(HERE.name + "__")
    folder = HERE / "current-runtime-selected-proof" / suffix / candidate
    folder.mkdir(parents=True, exist_ok=True)
    if suffix == "reference" and candidate == "primary":
        attempt = ROOT / ".runtime-work/c111331-current-reference-primary-compat"
        saved_dir = ROOT / ".runtime-work/c111331-current-reference-primary-saved"
        shutil.copyfile(HERE / "current-runtime-reference-primary-compat.log", folder / "compatibility.log")
        shutil.copyfile(HERE / "current-runtime-reference-primary-saved.log", folder / "process-saved.log")
        compat = json.loads((attempt / "compatibility.json").read_text())
        saved = json.loads((saved_dir / "v0001/processing.json").read_text())
    else:
        attempt = ROOT / ".runtime-work/c111331-current-matrix" / suffix / candidate / "compat"
        saved_dir = ROOT / ".runtime-work/c111331-current-matrix" / suffix / candidate / "saved"
        common = ["--manifest", str(MANIFEST), "--case", case, "--candidate", candidate]
        tool = [sys.executable, str(ROOT / "runtime.py")]
        options = ["--library", str(LIBRARY), "--validator", str(VALIDATOR)]
        if (attempt / "compatibility.json").is_file():
            compat = json.loads((attempt / "compatibility.json").read_text())
        else:
            compat = run([*tool, "compatibility", *common, "--output", str(attempt), *options],
                         folder / "compatibility.log")
        saved = run([*tool, "process-saved", "--manifest", str(MANIFEST), "--case", case,
                     "--attempt", str(attempt),
                     "--output", str(saved_dir), *options], folder / "process-saved.log")
    selected = entry if candidate == "primary" else next(
        row for row in entry["candidates"] if row["id"] == candidate)
    if not (compat.get("passed") is True and compat.get("case_id") == case and
            compat.get("candidate_id") == candidate and
            compat.get("construction_sha256") == selected["construction_sha256"] and
            compat.get("negative_removed") == "native_samples.jsonl" and
            saved.get("passed") is True and saved.get("recorded_only") is True and
            saved.get("case_id") == case and saved.get("candidate_id") == candidate and
            saved.get("originals_preserved") is True and not saved.get("missing_evidence") and
            saved["timestamp_joins"]["passed"] is True and
            saved["physical_acceptance_claimed"] is False and
            saved["legal_acceptance_claimed"] is False):
        raise ValueError("Selected proof differs: " + suffix + "/" + candidate)
    shutil.copyfile(attempt / "compatibility.json", folder / "compatibility.json")
    shutil.copyfile(saved_dir / "v0001/processing.json", folder / "saved-processing.json")
    shutil.copyfile(attempt / "compatibility-analysis.log", folder / "analysis.log")
    shutil.copyfile(attempt / "negative-analysis.log", folder / "negative-analysis.log")
    print(suffix, candidate, "compatibility and saved passed", flush=True)
    return {"case_id": case, "candidate_id": candidate,
            "construction_sha256": selected["construction_sha256"],
            "proof_dir": str(folder.relative_to(HERE)),
            "compatibility_sha256": sha(folder / "compatibility.json"),
            "saved_sha256": sha(folder / "saved-processing.json")}


def main():
    manifest = json.loads(MANIFEST.read_text())
    jobs = [(entry, candidate) for entry in manifest["cases"]
            for candidate in ("primary", "fallback1", "fallback2", "fallback3")]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(lambda job: task(*job), jobs))
    if len(rows) != 8:
        raise ValueError("Eight exact selected chains required")
    output = HERE / "current-runtime-matrix-progress.json"
    output.write_text(json.dumps({"format": "c111331-current-matrix-v1",
                                  "runtime_manifest_sha256": manifest["runtime_manifest_sha256"],
                                  "manifest_sha256": sha(MANIFEST), "completed": len(rows),
                                  "rows": rows, "original_native_accepted": False}, indent=2) + "\n")
    print(json.dumps({"chains": len(rows), "index_sha256": sha(output)}))


if __name__ == "__main__":
    main()
