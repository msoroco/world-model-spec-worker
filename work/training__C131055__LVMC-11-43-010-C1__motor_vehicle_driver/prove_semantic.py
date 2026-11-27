"""Validate the current-runtime canonical proposal chain for this assignment."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'runtime'))
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))

from scenario_pipeline.worker_exchange.semantic_delivery import validate


if __name__ == '__main__':
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    print(json.dumps(validate(HERE, assignment, manifest), sort_keys=True))
