"""Run the pinned canonical stage validator on this assignment's draft proposals."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNTIME = REPO / 'runtime/pipeline'
sys.path[:0] = [str(RUNTIME), str(RUNTIME / 'scenario_pipeline')]
from scenario_pipeline.worker_exchange.semantic_delivery import validate

folder = Path(__file__).resolve().parent
assignment = json.loads((REPO / 'inputs' / folder.name / 'assignment.json').read_text())
manifest = json.loads((folder / 'execution-manifest.json').read_text())
print(json.dumps(validate(folder, assignment, manifest), indent=2))
