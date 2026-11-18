"""Validate this assignment's saved canonical semantic stage chain on CPU."""
import json
from pathlib import Path
import sys

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate

assignment = json.loads((repo / 'inputs' / folder.name / 'assignment.json').read_text())
manifest = json.loads((folder / 'execution-manifest.json').read_text())
print(json.dumps(validate(folder, assignment, manifest), indent=2))
