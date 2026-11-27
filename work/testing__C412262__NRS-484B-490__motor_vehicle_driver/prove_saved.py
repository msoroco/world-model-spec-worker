"""Exercise saved-only revisions against every current exact diagnostic case."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / ".runtime-work/c412262-490-recorded-v1"
MANIFEST = HERE / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def call(argv, env):
    run = subprocess.run(argv, cwd=REPO, env=env, capture_output=True, text=True, timeout=600)
    if run.returncode:
        raise RuntimeError("saved diagnostic failed: " + (run.stdout + run.stderr)[-2500:])
    return json.loads(run.stdout)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    temp = ROOT / "tmp"
    temp.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(temp),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT))
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        tag = case_id.rsplit("__", 1)[1]
        fixture = ROOT / "fixture" / tag
        processed = ROOT / "processed" / tag
        for folder in (fixture, processed):
            if folder.exists():
                shutil.rmtree(folder)
            folder.parent.mkdir(parents=True, exist_ok=True)
        call([sys.executable, "runtime.py", "compatibility", "--manifest", str(MANIFEST),
              "--case", case_id, "--output", str(fixture), "--library", "runtime/library",
              "--validator", str(VALIDATOR)], env)
        before = {p.relative_to(fixture).as_posix(): sha(p) for p in fixture.rglob("*") if p.is_file()}
        result = call([sys.executable, "runtime.py", "process-saved", "--manifest", str(MANIFEST),
                       "--case", case_id, "--attempt", str(fixture), "--output", str(processed),
                       "--library", "runtime/library", "--validator", str(VALIDATOR)], env)
        after = {p.relative_to(fixture).as_posix(): sha(p) for p in fixture.rglob("*") if p.is_file()}
        if before != after or result.get("passed") is not True or result.get("recorded_only") is not True or result.get("originals_preserved") is not True or result.get("missing_evidence") is not False or result.get("physical_acceptance_claimed") is not False or result.get("legal_acceptance_claimed") is not False or result.get("timestamp_joins", {}).get("frames") != 9 or result.get("final_video_checks", {}).get("passed") is not True:
            raise ValueError("saved-only source, time or acceptance invariant failed: " + case_id)
        receipt = {"format": "diagnostic-recorded-only-cpu-proof", "case_id": case_id,
                   "source_kind": "synthetic_diagnostic_fixture", "passed": True,
                   "recorded_only": True, "originals_preserved": True,
                   "timestamp_joins": result["timestamp_joins"],
                   "final_video_checks": {"passed": True, "frames": result["final_video_checks"]["frames"]},
                   "analysis_log_sha256": result["analysis_log_sha256"],
                   "processing_sha256": sha(processed / "v0001/processing.json"),
                   "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}
        (HERE / ("cpu-recorded-" + tag + "-receipt.json")).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        content = "recorded-only diagnostic fixture passed for " + case_id + "; nine source-joined frames; original sources preserved; no physical or legal acceptance\n"
        log = HERE / entry["post_capture"]["test_log"]
        log.write_text(content)
        if sha(log) != entry["post_capture"]["test_log_sha256"]:
            raise ValueError("saved-only proof log differs from bound manifest")
        print(tag, "saved-only pass", flush=True)


if __name__ == "__main__":
    main()
