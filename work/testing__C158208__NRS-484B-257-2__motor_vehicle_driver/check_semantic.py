"""Check the authored semantic stages against the frozen exact assignment."""

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
ASSIGNMENT_ID = PACKAGE.name

output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
if not output_root or not Path(output_root).resolve().is_relative_to(ROOT / ".runtime-work"):
    raise ValueError("Use an output root under .runtime-work before importing runtime")

sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "runtime" / "scenario_pipeline"))
from worker_exchange.semantic_delivery import validate  # noqa: E402


def main():
    assignment = json.loads((ROOT / "inputs" / ASSIGNMENT_ID / "assignment.json").read_text())
    manifest = json.loads((PACKAGE / "execution-manifest.json").read_text())
    print(json.dumps(validate(PACKAGE, assignment, manifest), sort_keys=True))


if __name__ == "__main__":
    main()
