"""Re-run exact current-hash offline, compatibility and saved-only CPU proofs."""
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
MANIFEST = HERE / "execution-manifest.json"
PYTHON = str(REPO / ".venv-cpu/bin/python")
SCRATCH = REPO / ".runtime-work/c24757-owner"
VALIDATOR = REPO / ".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def call(cmd):
    done = subprocess.run(cmd, cwd=REPO, env=os.environ, capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError("CPU proof failed: " + " ".join(cmd) + "\n" + done.stderr[-3000:])
    return done.stdout


def save(name, source):
    path = HERE / name
    path.write_text(Path(source).read_text().rstrip() + "\n")
    return path


def prove():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        kind = entry["case_id"].removeprefix(HERE.name + "__")
        for candidate in ("primary", "fallback1"):
            tag = kind + "-" + candidate
            offline = SCRATCH / ("offline-full5-" + tag)
            command = [PYTHON, str(REPO / "runtime.py"), "offline", "--manifest", str(MANIFEST),
                       "--case", entry["case_id"], "--output", str(offline), "--python", PYTHON]
            if candidate != "primary":
                command.extend(("--candidate", candidate))
            call(command)
            log = save("cpu-offline-" + tag + ".log", offline / "offline.log")
            construction_sha = entry["construction_sha256"] if candidate == "primary" else entry["candidates"][0]["construction_sha256"]
            proof = {"command": " ".join(command), "construction_sha256": construction_sha,
                     "log": log.name, "log_sha256": sha(log), "exit_code": 0}
            if candidate == "primary":
                entry["offline"] = proof
            else:
                entry["candidates"][0]["offline"] = proof
            compat = SCRATCH / ("compat-full5-" + tag)
            ccmd = [PYTHON, str(REPO / "runtime.py"), "compatibility", "--manifest", str(MANIFEST),
                    "--case", entry["case_id"], "--output", str(compat),
                    "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
            if candidate != "primary":
                ccmd.extend(("--candidate", candidate))
            call(ccmd)
            analysis = save("cpu-compat-" + tag + "-analysis.log", compat / "compatibility-analysis.log")
            negative = save("cpu-compat-" + tag + "-negative.log", compat / "negative-analysis.log")
            receipt = HERE / ("cpu-compat-" + tag + "-receipt.json")
            shutil.copyfile(compat / "compatibility.json", receipt)
            spec = {"command": " ".join(ccmd), "log": analysis.name, "negative_log": negative.name,
                    "receipt": receipt.name, "sha256": sha(receipt), "negative_log_sha256": sha(negative)}
            if candidate == "primary":
                entry["compatibility"] = spec
                entry["negative"] = {"log": negative.name, "log_sha256": sha(negative)}
            else:
                entry["candidates"][0]["compatibility"] = spec
            print("offline+compat", tag, "passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    for entry in manifest["cases"]:
        kind = entry["case_id"].removeprefix(HERE.name + "__")
        attempt = SCRATCH / ("compat-full5-" + kind + "-primary")
        (attempt / "candidate-selection.json").unlink()
        output = SCRATCH / ("saved-full5-" + kind)
        cmd = [PYTHON, str(REPO / "runtime.py"), "process-saved", "--manifest", str(MANIFEST),
               "--case", entry["case_id"], "--attempt", str(attempt), "--output", str(output),
               "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
        positive = json.loads(call(cmd))
        if not positive["passed"] or positive["missing_evidence"] or not positive["originals_preserved"] or not positive["timestamp_joins"]["passed"]:
            raise ValueError("positive saved-only result incomplete: " + kind)
        log = HERE / ("cpu-saved-" + kind + ".log")
        log.write_text(json.dumps(positive, sort_keys=True, indent=2) + "\n")
        missing = SCRATCH / ("saved-full5-missing-attempt-" + kind)
        shutil.copytree(attempt, missing)
        (missing / "other-history.json").unlink()
        negative = SCRATCH / ("saved-full5-missing-" + kind)
        ncmd = cmd.copy()
        ncmd[ncmd.index("--attempt") + 1] = str(missing)
        ncmd[ncmd.index("--output") + 1] = str(negative)
        failure = json.loads(call(ncmd))
        if not failure["missing_evidence"] or "other-history.json" not in (negative / "v0001/feedback.json").read_text():
            raise ValueError("missing original speed history source not classified: " + kind)
        neglog = HERE / ("cpu-saved-" + kind + "-missing.log")
        neglog.write_text(json.dumps(failure, sort_keys=True, indent=2) + "\n")
        entry["post_capture"] = {"command": " ".join(cmd), "feedback_command": " ".join(ncmd),
                                 "test_log": log.name, "test_log_sha256": sha(log), "test_exit_code": 0,
                                 "feedback_log": neglog.name, "feedback_log_sha256": sha(neglog),
                                 "feedback_test_exit_code": 0, "recorded_only": True,
                                 "diagnostic_fixture": True, "physical_acceptance_claimed": False}
        print("saved-only positive+negative", kind, "passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    prove()
