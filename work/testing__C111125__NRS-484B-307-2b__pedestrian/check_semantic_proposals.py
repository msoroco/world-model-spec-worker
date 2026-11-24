"""Validate the source-hashed draft semantic stages against the pinned contract."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))

from worker_exchange.semantic_delivery import validate


if __name__ == '__main__':
    assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
    manifest = json.loads((ROOT / 'diagnostic-manifest.json').read_text())
    print(json.dumps(validate(ROOT, assignment, manifest), sort_keys=True))
