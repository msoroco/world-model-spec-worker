"""Bind six exact synthetic software compatibility receipts to the manifest."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
SCRATCH = REPO / ".runtime-work/c157964-nov27"
DECODER = REPO / ".runtime-work/c150099-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(entry, suffix, candidate, env):
    tag = suffix if candidate == "primary" else "fallback-" + suffix
    output = SCRATCH / ("compat-" + tag + "-v7")
    command = [sys.executable, str(REPO / "runtime.py"), "compatibility",
               "--manifest", str(MANIFEST), "--case", entry["case_id"],
               "--candidate", candidate, "--output", str(output),
               "--library", str(REPO / "runtime/library"),
               "--validator", str(DECODER)]
    process = subprocess.run(command, cwd=REPO, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if process.returncode:
        raise ValueError("compatibility failed: " + tag + "\n" + process.stdout[-1800:])
    targets = {"compatibility.json": "cpu-compat-" + tag + ".json",
               "compatibility-analysis.log": "cpu-compat-analysis-" + tag + ".log",
               "negative-analysis.log": "cpu-compat-negative-" + tag + ".log"}
    for source, target in targets.items():
        shutil.copyfile(output / source, ROOT / target)
        path = ROOT / target
        if path.suffix == ".log":
            data = path.read_text().rstrip()
            path.write_text(data + "\n" if data else "")
    receipt = json.loads((ROOT / targets["compatibility.json"]).read_text())
    if receipt.get("passed") is not True or receipt.get("case_id") != entry["case_id"] or \
            receipt.get("candidate_id") != candidate:
        raise ValueError("compatibility receipt identity differs")
    return {"receipt": targets["compatibility.json"],
            "sha256": sha(ROOT / targets["compatibility.json"]),
            "log": targets["compatibility-analysis.log"],
            "negative_log": targets["negative-analysis.log"]}


def main():
    if not DECODER.is_file():
        raise ValueError("pinned Lean decoder executable missing")
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               TMPDIR=str(SCRATCH), SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH))
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(ROOT.name + "__")
        entry["compatibility"] = prove(entry, suffix, "primary", env)
        entry["negative"] = {"log": entry["compatibility"]["negative_log"]}
        construction = json.loads((ROOT / entry["construction"]).read_text())
        entry["acquisition"] = {item["name"]: {
            "entrypoint": "analysis.py", "method": "saved_original_channel",
            "evidence": "channels/" + item["name"] + ".jsonl"}
            for item in construction["recording_description"]["channels"]}
        entry["acquisition"]["reviewed_officer_site_packet"] = {
            "entrypoint": "analysis.py", "method": "source-sealed original site packet",
            "evidence": "channels/context.json"}
        entry["candidates"][0]["compatibility"] = prove(entry, suffix, "fallback1", env)
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print("compatibility passed", suffix, "primary and fallback", flush=True)


if __name__ == "__main__":
    main()
