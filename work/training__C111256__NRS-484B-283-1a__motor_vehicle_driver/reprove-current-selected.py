"""Rerun exact selected 600-frame CPU paths against the frozen current manifest."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c111256-current"
MANIFEST = HERE / "execution-manifest.json"
VALIDATOR = ROOT / ".runtime-work/c110763-refresh/decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case, candidate, ref):
    key = case + "-" + candidate
    case_id = HERE.name + "__" + case
    folder = SCRATCH / key
    folder.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(TMPDIR=str(folder), SCENARIO_PIPELINE_OUTPUT_ROOT=str(folder),
               PYTHONDONTWRITEBYTECODE="1")
    offline, attempt, saved = (folder / name for name in ("offline", "compat", "saved"))
    steps = [
        ("offline", ["offline", "--manifest", MANIFEST, "--case", case_id,
                     "--candidate", candidate, "--output", offline]),
        ("compatibility", ["compatibility", "--manifest", MANIFEST, "--case", case_id,
                           "--candidate", candidate, "--output", attempt,
                           "--library", ROOT / "runtime/library", "--validator", VALIDATOR]),
        ("process-saved", ["process-saved", "--manifest", MANIFEST, "--case", case_id,
                           "--attempt", attempt, "--output", saved,
                           "--library", ROOT / "runtime/library", "--validator", VALIDATOR]),
    ]
    logs = {}
    for stage, args in steps:
        log = HERE / f"current-{stage}-{key}.log"
        with log.open("w") as stream:
            code = subprocess.run([sys.executable, str(ROOT / "runtime.py"),
                                   *map(str, args)], cwd=ROOT, env=env,
                                  stdout=stream, stderr=subprocess.STDOUT,
                                  timeout=900).returncode
        if code:
            raise RuntimeError(f"{key} {stage} exited {code}: {log.read_text()[-600:]}")
        logs[stage] = {"log": log.name, "log_sha256": sha(log), "exit_code": 0}
    receipt = json.loads((attempt / "compatibility.json").read_text())
    processing = json.loads((saved / "v0001/processing.json").read_text())
    if (receipt.get("passed") is not True or receipt.get("candidate_id") != candidate
            or receipt.get("construction_sha256") != ref["construction_sha256"]
            or receipt.get("negative_removed") != "road_geometry.json"
            or processing.get("passed") is not True or processing.get("recorded_only") is not True
            or processing.get("originals_preserved") is not True
            or processing.get("timestamp_joins", {}).get("frames") != 600):
        raise ValueError("Current exact source/saved proof differs: " + key)
    return key, {"case_id": case_id, "candidate": candidate,
                 "construction_sha256": ref["construction_sha256"],
                 "attempt": str(attempt.relative_to(ROOT)),
                 "saved": str(saved.relative_to(ROOT)),
                 "logs": logs,
                 "receipt_sha256": sha(attempt / "compatibility.json"),
                 "analysis_sha256": sha(attempt / "compatibility-analysis.log"),
                 "negative_sha256": sha(attempt / "negative-analysis.log"),
                 "processing_sha256": sha(saved / "v0001/processing.json")}


def main():
    manifest = json.loads(MANIFEST.read_text())
    if manifest["runtime_manifest_sha256"] != sha(ROOT / "runtime/SOURCE-MANIFEST.json"):
        raise ValueError("Selected manifest must pin active runtime")
    tasks = [(entry["case_id"].split("__")[-1], ref["id"], ref)
             for entry in manifest["cases"] for ref in
             [dict(entry, id="primary"), *entry["candidates"]]]
    paths = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_to_key = {pool.submit(run, *task): task[:2] for task in tasks}
        for future in as_completed(future_to_key):
            key, result = future.result()
            paths[key] = result
            print(key, result["receipt_sha256"], flush=True)
    proof = {"format": "c111256-current-selected-matrix-v1", "passed": True,
             "manifest_sha256": sha(MANIFEST), "runtime_manifest_sha256": manifest["runtime_manifest_sha256"],
             "path_count": len(paths), "paths": dict(sorted(paths.items())),
             "original_native_or_legal_claimed": False}
    path = HERE / "current-selected-matrix-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print("proof", sha(path), flush=True)


if __name__ == "__main__":
    main()
