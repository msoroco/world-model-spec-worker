"""Dispatch an exact selected C158208 construction with original-source gates."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def selected(case_id: str, candidate_id: str) -> dict:
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    matches = [item for item in manifest["cases"] if item["case_id"] == case_id]
    if len(matches) != 1:
        raise ValueError("unknown exact C158208 case")
    primary = matches[0]
    item = primary if candidate_id == "primary" else next(
        (item for item in primary["candidates"] if item["id"] == candidate_id), None)
    if item is None:
        raise ValueError("unknown exact engineering candidate")
    path = (HERE / item["construction"]).resolve()
    if HERE not in path.parents or hashlib.sha256(path.read_bytes()).hexdigest() != item["construction_sha256"]:
        raise ValueError("selected construction changed")
    bundle = json.loads(path.read_text())
    if bundle["case_id"] != case_id or bundle.get("diagnostic_only") is not False:
        raise ValueError("original source-gated construction required")
    return item


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", default="primary")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    selected(args.case, args.candidate)
    if args.check:
        print("source-gated exact construction selected")
        return
    if args.output_dir is None:
        raise ValueError("original Native output directory required")
    site = os.environ.get("C158208_REVIEWED_SITE", "")
    expected = os.environ.get("C158208_REVIEWED_SITE_SHA256", "")
    if not site or len(expected) != 64 or not Path(site).is_file() or hashlib.sha256(Path(site).read_bytes()).hexdigest() != expected:
        raise ValueError("source-hashed reviewed C158208 site required")
    scratch = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    scratch_path = Path(scratch).resolve() if scratch else None
    if scratch_path is None or ROOT / ".runtime-work" not in scratch_path.parents:
        raise ValueError("materialization root must be under .runtime-work")
    materialized = scratch_path / "c158208" / args.case.rsplit("__", 1)[-1] / args.candidate
    if materialized.exists():
        raise ValueError("retain prior materialization; use a new output root")
    subprocess.run([sys.executable, str(ROOT / "runtime.py"), "offline", "--manifest",
                    str(HERE / "execution-manifest.json"), "--case", args.case,
                    "--candidate", args.candidate, "--output", str(materialized),
                    "--python", sys.executable], check=True)
    carla_python = os.environ.get("CARLA_PYTHON", "")
    if not carla_python:
        raise ValueError("CARLA_PYTHON required for original Native capture")
    subprocess.run([carla_python, str(materialized / "runner.py"), "--output-dir",
                    str(args.output_dir), "--host", args.host, "--port", str(args.port)],
                   check=True)


if __name__ == "__main__":
    main()
