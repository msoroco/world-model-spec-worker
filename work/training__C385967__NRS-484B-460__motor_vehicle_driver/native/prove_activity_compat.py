"""Run pinned public compatibility for one explicit statutory action pair."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ROOT = HERE.parents[2]
ASSIGNMENT = FOLDER.name
VALIDATOR = ROOT / ".runtime-work/c385967-owner-decoder/.lake/build/bin/adapterCheck"


def run(action):
    for letter in "ab":
        case = ASSIGNMENT + f"__selected_03f318de__{action}_condition_{letter}"
        for candidate in ("primary", "fallback1"):
            prefix = f"selected-{action}-{letter}-{candidate}"
            output = ROOT / ".runtime-work" / f"c385967-{action}-{letter}-{candidate}-compat"
            command = [sys.executable, "-B", str(ROOT / "runtime.py"), "compatibility",
                "--manifest", str(FOLDER / "selected-compat-manifest.json"),
                "--case", case, "--candidate", candidate, "--output", str(output),
                "--library", str(ROOT / "runtime/library"), "--validator", str(VALIDATOR)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=1800)
            (HERE / f"{prefix}-compatibility.stdout.log").write_text(
                (result.stdout + result.stderr).rstrip() + "\n")
            if result.returncode:
                raise ValueError(f"{prefix} compatibility failed: " + result.stderr[-2500:])
            receipt = json.loads((output / "compatibility.json").read_text())
            if receipt.get("passed") is not True:
                raise ValueError(f"{prefix} compatibility did not pass")
            for source, target in (("compatibility.json", f"{prefix}-compatibility.json"),
                                   ("compatibility-analysis.log", f"{prefix}-compatibility-analysis.log"),
                                   ("negative-analysis.log", f"{prefix}-negative.log")):
                data = (output / source).read_text()
                (HERE / target).write_text(data)
            print(json.dumps({"case_id": case, "candidate": candidate,
                              "compatibility_passed": True}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("stop", "stand"), required=True)
    args = parser.parse_args()
    run(args.action)
