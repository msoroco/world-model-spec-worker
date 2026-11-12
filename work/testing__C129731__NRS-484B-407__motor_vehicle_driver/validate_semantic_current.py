"""Validate the current source-hashed semantic chain against all selected cases."""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))

from worker_exchange import semantic_delivery


def main():
    assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    report = semantic_delivery.validate(HERE, assignment, manifest)
    if report["selected_cases"] != len(manifest["cases"]):
        raise ValueError("Semantic validation omitted selected cases")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
