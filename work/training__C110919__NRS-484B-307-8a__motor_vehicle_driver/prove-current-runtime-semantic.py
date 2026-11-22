"""Validate the selected twenty-case semantic chain against the frozen runtime."""
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
if not output_root or ROOT / ".runtime-work" not in Path(output_root).resolve().parents:
    raise RuntimeError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0, str(ROOT / "runtime/pipeline"))
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from scenario_pipeline.worker_exchange.semantic_delivery import validate

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    result = validate(HERE, assignment, manifest)
    if result["selected_cases"] != 20:
        raise ValueError("Twenty selected semantic cases required")
    output = HERE / "current-runtime-selected-semantic-proof.json"
    output.write_text(json.dumps({
        "format": "c110919-current-semantic-proof-v1",
        "manifest_sha256": sha(manifest_path),
        "semantic_index_sha256": sha(HERE / "proposals/semantic-index.json"),
        "selected_cases": 20, "pinned_stage_chain_passed": True,
        "original_native_accepted": False
    }, indent=2) + "\n")
    print(json.dumps({"selected_cases": 20, "proof_sha256": sha(output)}))

if __name__ == "__main__":
    main()
