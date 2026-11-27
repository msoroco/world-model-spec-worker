"""Execute saved-only processing on current exact synthetic diagnostic sources."""
import hashlib
import json
import os
import shutil
import subprocess
from uuid import uuid4
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c398030/decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        source = REPO / ".runtime-work" / f"c398030/compat-update-{suffix}-primary"
        attempt = REPO / ".runtime-work" / f"c398030/saved-{suffix}-{uuid4().hex}-attempt"
        command = [str(REPO / ".venv-cpu/bin/python"), "runtime.py", "materialize",
                   "--manifest", str(MANIFEST), "--case", entry["case_id"],
                   "--output", str(attempt)]
        created = subprocess.run(command, cwd=REPO, env=os.environ.copy(),
                                 text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if created.returncode:
            raise RuntimeError(created.stdout[-1000:])
        receipt = json.loads((ROOT / f"compat-{suffix}-primary-receipt.json").read_text())
        for name in receipt["fixture_manifest"]:
            original = source / name
            if not original.is_file():
                raise RuntimeError("diagnostic source absent: " + name)
            target = attempt / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
        output = REPO / ".runtime-work" / f"c398030/saved-{suffix}-{uuid4().hex}"
        args = [str(REPO / ".venv-cpu/bin/python"), "runtime.py", "process-saved",
                "--manifest", str(MANIFEST), "--case", entry["case_id"],
                "--attempt", str(attempt), "--output", str(output),
                "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
        result = subprocess.run(args, cwd=REPO, env=os.environ.copy(), text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = ROOT / f"saved-{suffix}.log"
        log.write_text(result.stdout.rstrip() + "\n")
        if result.returncode:
            raise RuntimeError(f"{suffix}: {result.stdout[-1500:]}")
        entry["post_capture"] = {"recorded_only": True, "command": " ".join(args),
                                 "feedback_command": " ".join(args),
                                 "test_log": log.name, "test_log_sha256": sha(log),
                                 "test_exit_code": 0}
        MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
