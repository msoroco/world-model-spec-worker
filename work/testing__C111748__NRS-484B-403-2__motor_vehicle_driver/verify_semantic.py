"""CPU-check the exact canonical semantic stage chain for this assignment."""
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
if not output_root or not Path(output_root).resolve().is_relative_to(ROOT / ".runtime-work"):
    raise ValueError("set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime import")
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from worker_exchange.semantic_delivery import validate


def main() -> None:
    assignment = json.loads((ROOT / "inputs" / FOLDER.name / "assignment.json").read_text())
    manifest = json.loads((FOLDER / "execution-manifest.json").read_text())
    print(json.dumps(validate(FOLDER, assignment, manifest), sort_keys=True))


if __name__ == "__main__":
    main()
