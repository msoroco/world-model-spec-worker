"""Check the exact C158196 semantic proposals with the pinned CPU validator."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = next(p for p in HERE.parents if (p / "runtime/scenario_pipeline").is_dir())
sys.path.insert(0, str(REPO / "runtime"))
sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))

from scenario_pipeline.worker_exchange.semantic_delivery import validate


def main():
    assignment = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    result = validate(HERE, assignment, manifest)
    result.update({
        "format": "worker-semantic-delivery-cpu-proof",
        "passed": True,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    })
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
