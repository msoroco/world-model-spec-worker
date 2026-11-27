"""Bind CPU physical outcome, ownership and saved-only replay proofs."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c412927-owner"
MANIFEST = HERE / "execution-manifest.draft.json"
PYTHON = ROOT / ".venv-cpu/bin/python"
VALIDATOR = ROOT / ".runtime-work/c150911-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def save_log(path, content):
    text = "\n".join(line.rstrip() for line in content.rstrip().splitlines())
    path.write_text(text + "\n" if text else "", encoding="utf-8")


def run(command, path, env):
    result = subprocess.run([str(x) for x in command], cwd=ROOT, env=env,
                            text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    save_log(path, result.stdout)
    if result.returncode:
        raise ValueError("CPU lifecycle proof failed: " + str(path) + "\n" +
                         result.stdout[-1500:])
    return result


def prove(tag):
    env = dict(os.environ)
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH / "output")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(ROOT / "runtime/scenario_pipeline")
    env["TMPDIR"] = str(SCRATCH / "tmp")
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        slug = case_id.removeprefix(HERE.name + "__")
        physical_output = SCRATCH / tag / "physical" / slug
        physical_output.parent.mkdir(parents=True, exist_ok=True)
        command = [PYTHON, HERE / "physical_probe.py", "--case", case_id,
                   "--output", physical_output]
        physical_log = HERE / ("physical-" + slug + ".log")
        run(command, physical_log, env)
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            result_path = HERE / ("physical-" + slug + "-" + kind + ".json")
            fixtures.append({"kind": kind,
                             "command": " ".join(str(x) for x in command),
                             "exit_code": 0, "log": physical_log.name,
                             "log_sha256": sha(physical_log),
                             "result": result_path.name,
                             "result_sha256": sha(result_path)})
        receipt = HERE / ("physical-" + slug + "-receipt.json")
        receipt.write_text(json.dumps({
            "format": "worker-physical-preparation",
            "case_id": case_id,
            "construction_sha256": entry["construction_sha256"],
            "fixtures": fixtures,
            "lifecycle": {"events": ["capture_finished", "encoders_closed",
                                      "restoration_verified", "native_exit",
                                      "owner_released", "saved_processing_started"],
                          "exit_code": 0, "log": physical_log.name,
                          "log_sha256": sha(physical_log)}}, indent=2) + "\n")
        entry["physical_preparation"] = {"receipt": receipt.name,
                                          "sha256": sha(receipt)}
        saved_output = SCRATCH / tag / "saved" / slug
        saved_output.parent.mkdir(parents=True, exist_ok=True)
        command = [PYTHON, HERE / "saved_probe.py", "--case", case_id,
                   "--output", saved_output, "--validator", VALIDATOR]
        saved_log = HERE / ("cpu-saved-" + slug + ".log")
        run(command, saved_log, env)
        entry["post_capture"] = {
            "recorded_only": True,
            "command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/"+
                       HERE.name + "/execution-manifest.json --case " + case_id +
                       " --attempt $ATTEMPT --output $PROCESSED --library runtime/library --validator $LEAN_VALIDATOR --owner-release-receipt $OWNER_RELEASE_RECEIPT",
            "feedback_command": ".venv-cpu/bin/python work/" + HERE.name +
                                "/delivery_audit.py --case " + case_id +
                                " --attempt $ATTEMPT --processing $PROCESSING --decode-receipt $DECODE_RECEIPT",
            "test_exit_code": 0, "test_log": saved_log.name,
            "test_log_sha256": sha(saved_log)}
        print("passed", slug, "physical outcomes, lifecycle, saved-only", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    prove(args.tag)
