"""Run the pinned semantic stage validator on this exact six-case package."""

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate

assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
manifest = json.loads((HERE / 'execution-manifest.json').read_text())
print(validate(HERE, assignment, manifest))
