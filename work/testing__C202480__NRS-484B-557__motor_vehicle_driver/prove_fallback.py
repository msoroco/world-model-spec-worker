"""Test all source-hashed brake-margin alternatives through offline and Core."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / ".runtime-work/c202480-owner/fallback"
VALIDATOR = REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_copy(source: Path, target: Path) -> None:
    data = source.read_bytes()
    if data.endswith(b"\n\n"):
        raise ValueError("proof has blank final line")
    target.write_bytes(data)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT),
               TMPDIR=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        candidate = entry["candidates"][0]
        runtime = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py")]
        offline_output = ROOT / (suffix + "-offline")
        if offline_output.exists():
            shutil.rmtree(offline_output)
        offline_command = runtime + ["offline", "--manifest", str(path),
                                     "--case", entry["case_id"], "--candidate", "fallback1",
                                     "--output", str(offline_output), "--python",
                                     str(REPO / ".venv-cpu/bin/python")]
        done = subprocess.run(offline_command, cwd=REPO, env=env,
                              capture_output=True, text=True, timeout=300)
        if done.returncode:
            raise ValueError(suffix + " fallback offline failed: " + done.stderr[-1000:])
        offline_log = HERE / ("fallback-offline-" + suffix + ".log")
        exact_copy(offline_output / "offline.log", offline_log)
        candidate["offline"] = {
            "command": " ".join(offline_command).replace(str(REPO) + "/", ""),
            "exit_code": 0, "construction_sha256": candidate["construction_sha256"],
            "log": offline_log.name, "log_sha256": sha(offline_log)}
        output = ROOT / (suffix + "-compat")
        if output.exists():
            shutil.rmtree(output)
        command = runtime + ["compatibility", "--manifest", str(path),
                             "--case", entry["case_id"], "--candidate", "fallback1",
                             "--output", str(output), "--library", str(REPO / "runtime/library"),
                             "--validator", str(VALIDATOR)]
        done = subprocess.run(command, cwd=REPO, env=env,
                              capture_output=True, text=True, timeout=900)
        if done.returncode:
            raise ValueError(suffix + " fallback compatibility failed: " + done.stderr[-1200:])
        proof = json.loads((output / "compatibility.json").read_text())
        if proof.get("candidate_id") != "fallback1" or proof.get("passed") is not True:
            raise ValueError("fallback receipt candidate identity differs")
        receipt = HERE / ("fallback-compat-" + suffix + ".json")
        analysis_log = HERE / ("fallback-compat-analysis-" + suffix + ".log")
        negative_log = HERE / ("fallback-compat-negative-" + suffix + ".log")
        exact_copy(output / "compatibility.json", receipt)
        exact_copy(output / "compatibility-analysis.log", analysis_log)
        exact_copy(output / "negative-analysis.log", negative_log)
        candidate["compatibility"] = {
            "receipt": receipt.name, "sha256": sha(receipt),
            "log": analysis_log.name, "negative_log": negative_log.name}
        path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(suffix, "fallback1 offline and compatibility passed", flush=True)


if __name__ == "__main__":
    main()
