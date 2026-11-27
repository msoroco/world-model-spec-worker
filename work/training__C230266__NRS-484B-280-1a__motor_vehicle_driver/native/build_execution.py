"""Bind proved selected candidates into the exact-case execution manifest."""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
NATIVE = ROOT / "native"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT / "selected-compat-manifest.json").read_text())
    manifest["status"] = "cpu_proved_original_native_pending"
    for condition, entry in zip("ab", manifest["cases"]):
        case = entry["case_id"]
        source = REPO / f".runtime-work/c230266-release2-{condition}-positive-saved/v0001/processing.json"
        destination = NATIVE / f"selected-{condition}-saved-processing.json"
        shutil.copyfile(source, destination)
        log = NATIVE / f"selected-{condition}-saved.log"
        shutil.copyfile(REPO / f".runtime-work/c230266-release2-{condition}-positive-saved.stdout.json", log)
        proof = NATIVE / f"physical-{condition}/physical-preparation.json"
        entry["physical_preparation"] = {"receipt": str(proof.relative_to(ROOT)), "sha256": sha(proof)}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        entry["post_capture"] = {
            "recorded_only": True,
            "command": f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved --manifest work/{ROOT.name}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER",
            "feedback_command": f"cat $SAVED_OUTPUT/feedback.json # {case}",
            "test_command": f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved --manifest work/{ROOT.name}/selected-proof-manifest.json --case {case} --attempt .runtime-work/c230266-release2-{condition}-primary-compat --output .runtime-work/c230266-release2-{condition}-positive-saved --library runtime/library --validator .runtime-work/c385967-owner-decoder/.lake/build/bin/adapterCheck",
            "test_log": str(log.relative_to(ROOT)), "test_log_sha256": sha(log), "test_exit_code": 0,
            "receipt": str(destination.relative_to(ROOT)), "receipt_sha256": sha(destination)}
        negative = NATIVE / f"selected-{condition}-primary-negative-analysis.log"
        entry["negative"] = {"log": str(negative.relative_to(ROOT)), "log_sha256": sha(negative)}
    path = ROOT / "execution-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"manifest_sha256": sha(path), "cases": len(manifest["cases"])}))


if __name__ == "__main__":
    main()
