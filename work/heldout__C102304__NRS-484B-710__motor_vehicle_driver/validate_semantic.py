"""Validate the source-hashed canonical semantic chain for this exact assignment."""
import json
import sys
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parents[1]
sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate

assignment = json.loads((repo / 'inputs' / folder.name / 'assignment.json').read_text())
manifest = json.loads((folder / 'execution-manifest.json').read_text())
print(json.dumps(validate(folder, assignment, manifest), indent=2))
