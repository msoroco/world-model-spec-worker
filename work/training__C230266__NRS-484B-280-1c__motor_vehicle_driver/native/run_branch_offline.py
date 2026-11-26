"""Run current-runtime offline checks for every exact unselected construction."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parent.parent
ASSIGNMENT = ROOT.name


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = ROOT / "draft-all-branches-manifest.json"
    cases = json.loads(manifest.read_text())["cases"]
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    checks = []
    with tempfile.TemporaryDirectory(prefix="nrs280-offline-", dir=scratch) as temporary:
        for entry in cases:
            cid = entry["case_id"]
            suffix = cid.removeprefix(ASSIGNMENT + "__")
            output = Path(temporary) / suffix
            command = [str(REPO / ".venv-cpu/bin/python"), "-B", "runtime.py", "offline",
                       "--manifest", str(manifest.relative_to(REPO)), "--case", cid,
                       "--output", str(output)]
            completed = subprocess.run(command, cwd=REPO, capture_output=True,
                                       text=True, env=os.environ.copy())
            log_text = (completed.stdout + completed.stderr).rstrip() + "\n"
            staged = Path(temporary) / (suffix + "-offline.log")
            staged.write_text(log_text)
            log = HERE / "branch-cases" / staged.name
            os.replace(staged, log)
            checks.append({"case_id": cid, "exit_code": completed.returncode,
                           "log": str(log.relative_to(ROOT)), "log_sha256": digest(log),
                           "offline_passed": completed.returncode == 0})
            print(suffix, completed.returncode, flush=True)
        proof = {"format": "worker-nrs280-unselected-offline-index-v1",
                 "manifest_sha256": digest(manifest), "checks": checks,
                 "pass_count": sum(item["offline_passed"] for item in checks),
                 "physical_execution_proven": False}
        staged = Path(temporary) / "branch-offline-index.json"
        staged.write_text(json.dumps(proof, indent=2) + "\n")
        os.replace(staged, HERE / "branch-cases/branch-offline-index.json")
    if proof["pass_count"] != len(cases):
        raise ValueError("One or more exact offline constructions failed")


if __name__ == "__main__":
    main()
