"""Exercise selected saved-only processing from fresh diagnostic acquisitions."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parents[1]
MANIFEST = WORK / "execution-manifest.json"
SCRATCH = ROOT / ".runtime-work"
os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH / "c202465-saved-env")
os.environ["TMPDIR"] = str(SCRATCH)
sys.path[:0] = [str(ROOT / "runtime"), str(ROOT / "runtime/scenario_pipeline")]

from scenario_pipeline.worker_exchange.fixture_recipe import materialize as fixture_materialize
from scenario_pipeline.worker_exchange.runtime_cli import materialize as construction_materialize

VALIDATOR = SCRATCH / "c179480/decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    scratch = SCRATCH / ("c202465-lvmc-saved-" + str(time.time_ns()))
    scratch.mkdir(parents=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.split("__")[-1]
        attempt = scratch / suffix / "attempt"
        fixture = scratch / suffix / "fixture"
        output = scratch / suffix / "saved"
        attempt.parent.mkdir(parents=True)
        construction_materialize(MANIFEST, case_id, attempt, "primary")
        fixture_materialize(ROOT, ROOT / entry["fixture_recipe"], fixture)
        for source in fixture.iterdir():
            target = attempt / source.name
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copyfile(source, target)
        command = [sys.executable, "-B", str(ROOT / "runtime.py"), "process-saved",
                   "--manifest", str(MANIFEST), "--case", case_id,
                   "--attempt", str(attempt), "--output", str(output),
                   "--library", str(ROOT / "runtime/library"),
                   "--validator", str(VALIDATOR)]
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        proof_folder = WORK / "saved-proofs" / suffix
        proof_folder.mkdir(parents=True, exist_ok=True)
        log = proof_folder / "positive.log"
        log.write_text((run.stdout + run.stderr).rstrip() + "\n")
        if run.returncode:
            raise RuntimeError("Saved-only processing failed " + suffix + ": " + log.read_text()[-2000:])
        receipt = json.loads((output / "v0001/processing.json").read_text())
        if (receipt.get("passed") is not True or receipt.get("recorded_only") is not True
                or receipt.get("case_id") != case_id
                or receipt.get("native_revision", {}).get("construction_sha256") != entry["construction_sha256"]
                or receipt.get("timestamp_joins", {}).get("frames") != 600
                or receipt.get("final_video_checks", {}).get("frames") != 600):
            raise ValueError("Selected saved-only proof incomplete: " + suffix)
        entry["post_capture"] = {
            "recorded_only": True,
            "command": ("runtime.py process-saved --manifest work/" + WORK.name +
                        "/execution-manifest.json --case " + case_id +
                        " --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER"),
            "feedback_command": "cat $SAVED_OUTPUT/feedback.json # " + case_id,
            "test_log": str(log.relative_to(WORK)), "test_log_sha256": sha(log),
            "test_exit_code": 0,
        }
        entry["saved_proof"] = {"processing": str(output / "v0001/processing.json"),
                                "processing_sha256": sha(output / "v0001/processing.json"),
                                "attempt": str(attempt)}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
        print("PASS saved-only", suffix, flush=True)


if __name__ == "__main__":
    main()
