"""Bind diagnostic compatibility and missing-source proofs for exact cases."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
SCRATCH = REPO / ".runtime-work/c111329-compat"
LIBRARY = REPO / ".runtime-work/c111329-validator/library"
VALIDATOR = REPO / ".runtime-work/c111329-validator/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    if not VALIDATOR.is_file():
        raise ValueError("C111329 validator has not been built")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        for candidate, selected in [("primary", entry)] + [(item["id"], item) for item in entry["candidates"]]:
            output = SCRATCH / suffix / candidate
            if output.exists():
                shutil.rmtree(output)
            output.parent.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, "runtime.py", "compatibility", "--manifest",
                       str(MANIFEST.relative_to(REPO)), "--case", entry["case_id"],
                       "--output", str(output.relative_to(REPO)), "--library",
                       str(LIBRARY.relative_to(REPO)), "--validator", str(VALIDATOR.relative_to(REPO)),
                       "--candidate", candidate]
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / ".runtime-work/c111329-output"))
            result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(f"compatibility failed {suffix}/{candidate}: {(result.stdout + result.stderr)[-2000:]}")
            proof = json.loads((output / "compatibility.json").read_text())
            if not proof["passed"] or proof["candidate_id"] != candidate:
                raise ValueError("selected compatibility proof mismatch")
            receipt_path = ROOT / f"cpu-compatibility-{suffix}-{candidate}.json"
            log_path = ROOT / f"cpu-compatibility-{suffix}-{candidate}.log"
            negative_path = ROOT / f"cpu-negative-{suffix}-{candidate}.log"
            dump(receipt_path, proof)
            shutil.copyfile(output / "compatibility-analysis.log", log_path)
            shutil.copyfile(output / "negative-analysis.log", negative_path)
            negative_path.write_text(negative_path.read_text().rstrip() + "\n")
            if sha(log_path) != proof["log_sha256"] or sha(negative_path) != proof["negative_log_sha256"]:
                raise ValueError("compatibility logs differ from receipt")
            selected["compatibility"] = {"command": " ".join(command),
                                          "receipt": receipt_path.name, "sha256": sha(receipt_path),
                                          "log": log_path.name, "negative_log": negative_path.name}
            selected["negative"] = {"log": negative_path.name}
            if candidate == "primary":
                entry["acquisition"] = {name: {
                    "entrypoint": "runner.py", "method": "original Native synchronized capture",
                    "evidence": "source-gated original bicycle, governed device, officer and camera readback"}
                    for name in ("bicycle_front_body_position", "bicycle_speed",
                                 "device_instruction", "police_officer_direction")}
            dump(MANIFEST, manifest)
            print("passed", suffix, candidate)


if __name__ == "__main__":
    main()
