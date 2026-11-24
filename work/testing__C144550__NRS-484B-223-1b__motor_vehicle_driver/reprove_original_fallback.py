"""Replay and bind one retained original fallback with the current CPU runtime."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
VALIDATOR = ".runtime-work/c144550-decoder-current/.lake/build/bin/adapterCheck"
ORIGINAL = ("left_signal_before_clear_gap", "left_signal_late_clear_gap",
            "left_wrong_signal_clear_gap", "left_signal_before_close_gap",
            "right_signal_before_clear_gap")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log):
    with log.open("w") as stream:
        result = subprocess.run(command, cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                                stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        raise ValueError("CPU proof failed; inspect " + str(log.relative_to(ROOT)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suffix", choices=ORIGINAL, required=True)
    parser.add_argument("--candidate", choices=("fallback1", "fallback2", "fallback3"), required=True)
    arguments = parser.parse_args()
    suffix, candidate_id = arguments.suffix, arguments.candidate
    manifest = json.loads(MANIFEST.read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"].endswith("__" + suffix))
    candidate = next(item for item in entry["candidates"] if item["id"] == candidate_id)
    tag = "c144550-current-fallback-" + suffix + "-" + candidate_id + "-20261124"
    attempt = ROOT / ".runtime-work" / tag
    saved = ROOT / ".runtime-work" / (tag + "-saved")
    target = HERE / "cases" / suffix
    positive_log = target / (candidate_id + "-current-compatibility.log")
    saved_log = target / (candidate_id + "-current-saved.log")
    if attempt.exists() or saved.exists():
        raise ValueError("Current proof output already exists: " + tag)
    base = [str(ROOT / ".venv-cpu/bin/python"), str(ROOT / "runtime.py")]
    parameters = ["--manifest", str(MANIFEST), "--case", entry["case_id"]]
    codec = ["--library", str(ROOT / "runtime/library"),
             "--validator", str(ROOT / VALIDATOR)]
    run(base + ["compatibility"] + parameters + ["--candidate", candidate_id,
        "--output", str(attempt)] + codec, positive_log)
    proof = json.loads((attempt / "compatibility.json").read_text())
    if (proof.get("passed") is not True or proof.get("case_id") != entry["case_id"]
            or proof.get("candidate_id") != candidate_id
            or proof.get("construction_sha256") != candidate["construction_sha256"]
            or proof.get("runtime_manifest_sha256") != manifest["runtime_manifest_sha256"]):
        raise ValueError("Current fallback receipt does not bind selected construction/runtime")
    run(base + ["process-saved"] + parameters + ["--attempt", str(attempt),
        "--output", str(saved)] + codec, saved_log)
    processing = saved / "v0001/processing.json"
    if not processing.is_file():
        raise ValueError("Recorded-only processing receipt missing")
    sources = {"compatibility.json": attempt / "compatibility.json",
               "analysis.log": attempt / "compatibility-analysis.log",
               "negative.log": attempt / "negative-analysis.log",
               "processing.json": processing}
    names = {kind: candidate_id + "-current-" + kind for kind in sources}
    for kind, source in sources.items():
        shutil.copyfile(source, target / names[kind])
    prefix = "cases/" + suffix + "/"
    candidate["compatibility"] = {
        "receipt": prefix + names["compatibility.json"],
        "sha256": sha(target / names["compatibility.json"]),
        "log": prefix + names["analysis.log"],
        "negative_log": prefix + names["negative.log"],
        "replay_command": " ".join([".venv-cpu/bin/python", "runtime.py", "compatibility",
                                    "--manifest", "work/" + HERE.name + "/execution-manifest.json",
                                    "--case", entry["case_id"], "--candidate", candidate_id,
                                    "--output", ".runtime-work/" + tag,
                                    "--library", "runtime/library", "--validator", VALIDATOR]),
    }
    post = candidate["post_capture"]
    post.update({"recorded_only": True,
                 "command": " ".join([".venv-cpu/bin/python", "runtime.py", "process-saved",
                                      "--manifest", "work/" + HERE.name + "/execution-manifest.json",
                                      "--case", entry["case_id"], "--attempt", ".runtime-work/" + tag,
                                      "--output", ".runtime-work/" + tag + "-saved",
                                      "--library", "runtime/library", "--validator", VALIDATOR]),
                 "test_log": prefix + names["processing.json"],
                 "test_log_sha256": sha(target / names["processing.json"]),
                 "test_exit_code": 0,
                 "processing_receipt": prefix + names["processing.json"],
                 "processing_sha256": sha(target / names["processing.json"]),
                 "feedback_command": "cat $OUTPUT/feedback.json"})
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print("PASS", entry["case_id"], candidate_id, proof["runtime_manifest_sha256"])


if __name__ == "__main__":
    main()
