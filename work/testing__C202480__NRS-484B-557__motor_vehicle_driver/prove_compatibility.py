"""Run exact nine-case positive and missing-source CPU compatibility proofs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / ".runtime-work/c202480-owner"
VALIDATOR = REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keep(source: Path, target: Path) -> None:
    data = source.read_bytes()
    if data.endswith(b"\n\n") or any(line.rstrip(b" \t\r\n") != line.rstrip(b"\r\n")
                                     for line in data.splitlines(keepends=True)):
        raise ValueError("compatibility proof log needs whitespace review: " + str(source))
    target.write_bytes(data)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT),
               TMPDIR=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        output = ROOT / ("compat-" + suffix + "-positive")
        if suffix == "inside_15" and not output.exists():
            output = ROOT / "compat-inside-15-v5"
        cached = json.loads((output / "compatibility.json").read_text()) if (
            output / "compatibility.json").is_file() else {}
        recipe = REPO / entry["fixture_recipe"]
        contract = HERE / entry["measurement_contract"]
        current = (cached.get("passed") is True
                   and cached.get("construction_sha256") == entry["construction_sha256"]
                   and cached.get("fixture_recipe_sha256") == sha(recipe)
                   and cached.get("measurement_contract_sha256") == sha(contract))
        if not current:
            if output.exists():
                shutil.rmtree(output)
            command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                       "compatibility", "--manifest", str(manifest_path),
                       "--case", entry["case_id"], "--candidate", "primary",
                       "--output", str(output), "--library", str(REPO / "runtime/library"),
                       "--validator", str(VALIDATOR)]
            done = subprocess.run(command, cwd=REPO, env=env,
                                  capture_output=True, text=True, timeout=900)
            if done.returncode:
                raise ValueError(suffix + " compatibility failed: " + done.stderr[-1200:])
        proof = json.loads((output / "compatibility.json").read_text())
        if proof.get("passed") is not True or proof.get("case_id") != entry["case_id"]:
            raise ValueError("wrong exact-case compatibility receipt")
        receipt = HERE / ("primary-compat-" + suffix + ".json")
        log = HERE / ("primary-compat-analysis-" + suffix + ".log")
        negative = HERE / ("primary-compat-negative-" + suffix + ".log")
        keep(output / "compatibility.json", receipt)
        keep(output / "compatibility-analysis.log", log)
        keep(output / "negative-analysis.log", negative)
        entry["compatibility"] = {"receipt": receipt.name, "sha256": sha(receipt),
                                   "log": log.name, "negative_log": negative.name}
        entry["negative"] = {"log": negative.name}
        entry["acquisition"] = {
            "rail_stop": {"entrypoint": "native_capture.py", "method":
                          "source-hashed original Native speed, footprint and nearest rail line",
                          "evidence": "rail-stop-packet.json"},
            "crossing_conflict_history": {"entrypoint": "native_capture.py", "method":
                                          "source-hashed per-frame conflict body or explicit absence",
                                          "evidence": "native-conflict-history.json"},
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(suffix, "compatibility passed", flush=True)


if __name__ == "__main__":
    main()
