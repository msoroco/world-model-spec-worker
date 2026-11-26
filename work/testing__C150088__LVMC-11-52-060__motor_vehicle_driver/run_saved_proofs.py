"""Exercise selected saved-only processing from a copied CPU diagnostic attempt."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
SCRATCH = REPO / ".runtime-work/c150088-nov26/saved-proofs-v2"
VALIDATOR = REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        source = REPO / ".runtime-work/c150088-nov26/proofs-v5" / (suffix + "-primary/compat")
        attempt = SCRATCH / (suffix + "-attempt")
        if attempt.exists():
            shutil.rmtree(attempt)
        shutil.copytree(source, attempt)
        selection = attempt / "candidate-selection.json"
        if selection.exists():
            selection.unlink()
        output = SCRATCH / (suffix + "-output")
        command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                   "process-saved", "--manifest", str(MANIFEST), "--case", entry["case_id"],
                   "--attempt", str(attempt), "--output", str(output),
                   "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
        completed = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
        log = ROOT / ("cpu-saved-" + suffix + ".log")
        log.write_text((completed.stdout + completed.stderr).rstrip() + "\n", encoding="utf-8")
        if completed.returncode:
            raise RuntimeError(suffix + ": " + log.read_text()[-1500:])
        proof = json.loads((output / "v0001/processing.json").read_text(encoding="utf-8"))
        if (proof["passed"] is not True or proof["recorded_only"] is not True or
                proof["case_id"] != entry["case_id"] or not proof["originals_preserved"] or
                proof["missing_evidence"]):
            raise ValueError("saved-only proof did not complete: " + suffix)
        entry["post_capture"] = {"recorded_only": True, "command": " ".join(command),
                                 "feedback_command": " ".join(command),
                                 "test_exit_code": 0, "test_log": log.name,
                                 "test_log_sha256": sha(log)}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(suffix, "passed", flush=True)


if __name__ == "__main__":
    main()
