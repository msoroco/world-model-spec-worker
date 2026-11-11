"""Validate the C111706 stage chain against frozen scope and four selected cases."""

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate


if __name__ == '__main__':
    assignment = json.loads((ROOT / 'inputs' / FOLDER.name / 'assignment.json').read_text())
    manifest = json.loads((FOLDER / 'first-provisional-manifest.json').read_text())
    print(json.dumps(validate(FOLDER, assignment, manifest), sort_keys=True))
