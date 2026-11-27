"""Execute saved-only finalization for every exact diagnostic acquisition."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


REPO = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
SCRATCH = REPO / ".runtime-work" / "c229813-owner"
MANIFEST = PACKAGE / "execution-manifest.draft.json"
VALIDATOR = REPO / ".runtime-work/c150911-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    results = []
    env = dict(os.environ)
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.removeprefix(PACKAGE.name + "__")
        source = SCRATCH / "compat-all-v2" / (suffix + "-primary")
        attempt = SCRATCH / "saved-attempts-v2" / suffix
        if attempt.exists():
            raise ValueError("scratch attempt already exists: " + str(attempt))
        attempt.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, attempt)
        selection = attempt / "candidate-selection.json"
        if selection.is_file():
            selection.unlink()
        output = SCRATCH / "saved-outputs-v2" / suffix
        command = [sys.executable, str(REPO / "runtime.py"), "process-saved",
            "--manifest", str(MANIFEST), "--case", case_id,
            "--attempt", str(attempt), "--output", str(output),
            "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
        run = subprocess.run(command, cwd=REPO, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = PACKAGE / f"proof-saved-{suffix}.log"
        log.write_text(run.stdout.rstrip() + "\n")
        proof_path = output / "v0001/processing.json"
        passed = bool(run.returncode == 0 and proof_path.is_file() and
                      json.loads(proof_path.read_text()).get("passed"))
        results.append({"case_id": case_id, "command": " ".join(command),
                        "exit_code": run.returncode, "passed": passed,
                        "log": log.name, "log_sha256": sha(log),
                        "receipt": str(proof_path.relative_to(REPO))})
        print(suffix, "PASS" if passed else "FAIL", flush=True)
        if not passed:
            print(log.read_text()[-4000:], flush=True)
    (PACKAGE / "cpu-saved-proofs.json").write_text(json.dumps(results, indent=2) + "\n")
    return 0 if all(x["passed"] for x in results) else 1


if __name__ == "__main__":
    sys.exit(main())
