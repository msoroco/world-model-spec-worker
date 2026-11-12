"""Validate the frozen six-stage proposal chain and reject a stale source hash."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path[:0] = [str(REPO / "runtime"), str(REPO / "runtime/scenario_pipeline")]

from scenario_pipeline.worker_exchange.semantic_delivery import validate
from scenario_pipeline.worker_exchange import semantic_delivery


def main():
    assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    manifest = json.loads((ROOT / "probe-compatibility-manifest.json").read_text())
    receipt = validate(ROOT, assignment, manifest)
    original_read = semantic_delivery.read

    def stale_index(path):
        value = original_read(path)
        if Path(path).name == "semantic-index.json":
            value = copy.deepcopy(value)
            value["stages"]["cases"]["sha256"] = "0" * 64
        return value

    semantic_delivery.read = stale_index
    try:
        try:
            validate(ROOT, assignment, manifest)
        except ValueError as exc:
            if "source hash changed" not in str(exc):
                raise
        else:
            raise AssertionError("Stale proposal hash was accepted")
    finally:
        semantic_delivery.read = original_read
    print(json.dumps({**receipt, "stale_hash_rejected": True}, sort_keys=True))


if __name__ == "__main__":
    main()
