"""Validate the current C230671 canonical stage proposals against selected cases."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT/'runtime'), str(ROOT/'runtime/scenario_pipeline')]
from scenario_pipeline.worker_exchange.semantic_delivery import validate


def main():
    assignment = json.loads((ROOT/'inputs'/HERE.name/'assignment.json').read_text())
    manifest = json.loads((HERE/'execution-manifest.json').read_text())
    print(json.dumps(validate(HERE, assignment, manifest), sort_keys=True))


if __name__ == '__main__':
    main()
