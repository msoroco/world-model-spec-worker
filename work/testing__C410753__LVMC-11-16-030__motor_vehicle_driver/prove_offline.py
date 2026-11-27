"""Materialize and check every selected railway primary bundle on the CPU."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    scratch = REPO / ".runtime-work" / "c410753-offline"
    scratch.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="exact-seven-", dir=scratch))
    env = dict(os.environ,
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(root / "pipeline-output"),
               PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(root))
    manifest = HERE / "execution-manifest.json"
    entries = json.loads(manifest.read_text())["cases"]
    if len(entries) != 7:
        raise ValueError("seven exact railway cases required")
    for entry in entries:
        case_id = entry["case_id"]
        key = case_id.removeprefix(HERE.name + "__")
        if case_id != HERE.name + "__" + key:
            raise ValueError("selected railway case differs")
        command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                   "offline", "--manifest", str(manifest), "--case", case_id,
                   "--output", str(root / key),
                   "--python", str(REPO / ".venv-cpu/bin/python")]
        completed = subprocess.run(command, env=env, capture_output=True, text=True,
                                   timeout=300, check=True)
        print(key, "offline exit=0", completed.stdout.strip())
    print("seven exact primary railway offline bundles passed")


if __name__ == "__main__":
    main()
