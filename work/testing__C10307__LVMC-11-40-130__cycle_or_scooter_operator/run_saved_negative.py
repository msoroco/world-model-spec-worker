"""Exercise missing-context feedback in pinned saved processing for five cases."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c10307-decoder/.lake/build/bin/adapterCheck"


def main():
    manifest = json.loads(MANIFEST.read_text())
    manifest_hash = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    for entry in manifest["cases"]:
        case = entry["case_id"]
        short = case.removeprefix(ROOT.name + "__")
        source = REPO / ".runtime-work" / ("c10307-saved-v16-" + short + "-attempt")
        attempt = REPO / ".runtime-work" / ("c10307-saved-v16-" + short + "-negative-attempt")
        output = REPO / ".runtime-work" / ("c10307-saved-v16-" + short + "-negative-source")
        for path in (attempt, output):
            if path.exists():
                shutil.rmtree(path)
        shutil.copytree(source, attempt)
        (attempt / "context.json").unlink()
        selection = attempt / "candidate-selection.json"
        if selection.is_file():
            data = json.loads(selection.read_text())
            data["manifest_sha256"] = manifest_hash
            selection.write_text(json.dumps(data) + "\n")
        command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"), "process-saved",
                   "--manifest", str(MANIFEST), "--case", case,
                   "--attempt", str(attempt), "--output", str(output),
                   "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
        done = subprocess.run(command, cwd=REPO, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=600)
        log = ROOT / ("cpu-process-saved-negative-" + short + ".log")
        log.write_text(done.stdout)
        feedback = json.loads((output / "v0001/feedback.json").read_text())
        if (done.returncode == 0 or "Missing required source: context.json" not in feedback["error"]
                or feedback["native_replay_requested"] is not False):
            raise ValueError("saved processing failed to reject missing context: " + short)
        print(short, "missing source rejected", done.returncode, flush=True)


if __name__ == "__main__":
    main()
