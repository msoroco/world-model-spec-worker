"""Run and pin synthetic positive/negative compatibility for every case/candidate."""
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


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    py = str(REPO / ".venv-cpu/bin/python")
    runtime = str(REPO / "runtime.py")
    validator = str(REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck")
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       TMPDIR=str(REPO / ".runtime-work/c111278-owner/tmp"),
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / ".runtime-work/c111278-owner/pipeline"))
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        for candidate, holder in (("primary", entry), ("fallback1", entry["candidates"][0])):
            base = REPO / ".runtime-work/c111278-owner"
            version = 0
            while True:
                output = base / f"compat-{suffix}-{candidate}-{version}"
                if not output.exists():
                    break
                version += 1
            command = [py, runtime, "compatibility", "--manifest", str(MANIFEST),
                       "--case", entry["case_id"], "--output", str(output),
                       "--library", str(REPO / "runtime/library"),
                       "--validator", validator, "--candidate", candidate]
            run = subprocess.run(command, env=environment, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if run.returncode:
                raise RuntimeError(f"{suffix}/{candidate}: {run.stdout[-3000:]}")
            receipt = json.loads((output / "compatibility.json").read_text())
            if (receipt.get("passed") is not True or
                    receipt.get("construction_sha256") != holder["construction_sha256"] or
                    receipt.get("candidate_id") != candidate):
                raise ValueError("compatibility receipt does not bind selected construction")
            tag = suffix + "-" + candidate
            spec = {}
            for key, source, ending in (("receipt", "compatibility.json", "-receipt.json"),
                                        ("log", "compatibility-analysis.log", "-analysis.log"),
                                        ("negative_log", "negative-analysis.log", "-negative.log")):
                target = ROOT / ("compat-" + tag + ending)
                shutil.copyfile(output / source, target)
                spec[key] = target.name
                if key == "receipt":
                    spec["sha256"] = sha(target)
            spec["command"] = " ".join(command)
            holder["compatibility"] = spec
            print(suffix, candidate, "compatibility passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
