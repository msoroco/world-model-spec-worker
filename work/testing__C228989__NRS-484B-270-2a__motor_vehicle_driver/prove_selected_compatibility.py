"""Run exact positive/negative CPU compatibility on all selected pass cases."""

import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.selected-draft.json"
SCRATCH = ROOT / ".runtime-work" / "c228989-owner-nov26" / "selected-compat-v5"
VALIDATOR = ROOT / ".runtime-work" / "c110969-decoder" / ".lake" / "build" / "bin" / "adapterCheck"


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    if not VALIDATOR.is_file():
        raise ValueError("pinned Lean validator executable missing")
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["cases"]
    for entry in entries:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        destination = SCRATCH / suffix
        if destination.exists():
            raise ValueError("retain prior compatibility proof")
        command = [sys.executable, str(ROOT / "runtime.py"), "compatibility",
                   "--manifest", str(MANIFEST), "--case", entry["case_id"],
                   "--output", str(destination), "--library", str(ROOT / "runtime" / "library"),
                   "--validator", str(VALIDATOR)]
        env = dict(os.environ)
        env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH)
        env["TMPDIR"] = str(SCRATCH)
        result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        command_log = HERE / ("proof-compat-command-" + suffix + ".log")
        command_log.write_text(result.stdout.rstrip() + "\n", encoding="utf-8")
        if result.returncode:
            raise ValueError("selected compatibility failed: " + entry["case_id"])
        receipt = json.loads((destination / "compatibility.json").read_text(encoding="utf-8"))
        if receipt.get("passed") is not True or receipt.get("case_id") != entry["case_id"]:
            raise ValueError("incomplete exact compatibility receipt")
        for source, target in (("compatibility.json", "proof-compat-receipt-" + suffix + ".json"),
                               ("compatibility-analysis.log", "proof-compat-analysis-" + suffix + ".log"),
                               ("negative-analysis.log", "proof-compat-negative-" + suffix + ".log")):
            (HERE / target).write_bytes((destination / source).read_bytes())
    return len(entries)


if __name__ == "__main__":
    print("selected compatibility proofs:", run())
