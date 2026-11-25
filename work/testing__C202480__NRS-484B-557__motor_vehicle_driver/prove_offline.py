"""Run every exact primary construction through the pinned offline entrypoint."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main() -> None:
    root = REPO / ".runtime-work/c202480-owner"
    root.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(root),
               TMPDIR=str(root), PYTHONDONTWRITEBYTECODE="1")
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.removeprefix(HERE.name + "__")
        output = root / ("offline-" + suffix.replace("_", "-"))
        if output.exists():
            shutil.rmtree(output)
        command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                   "offline", "--manifest", str(manifest_path), "--case", case_id,
                   "--output", str(output), "--python", str(REPO / ".venv-cpu/bin/python")]
        done = subprocess.run(command, cwd=REPO, env=env,
                              capture_output=True, text=True, timeout=600)
        log = HERE / ("proof-offline-" + suffix + ".log")
        content = (done.stdout + done.stderr).rstrip("\n") + "\n"
        if (output / "offline.log").is_file():
            content += (output / "offline.log").read_text().rstrip("\n") + "\n"
        log.write_text(content, encoding="utf-8")
        if done.returncode:
            raise ValueError(f"exact offline failed for {suffix}: {done.stderr[-600:]}")
        entry["offline"] = {
            "command": " ".join(command).replace(str(REPO) + "/", ""),
            "exit_code": 0, "construction_sha256": entry["construction_sha256"],
            "log": log.name, "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()}
        print(suffix, "offline passed", flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
