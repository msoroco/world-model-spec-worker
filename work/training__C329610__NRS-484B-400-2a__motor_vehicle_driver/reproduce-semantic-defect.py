"""Reproduce the frozen law_record/law mismatch without editing inputs."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
FOLDER=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate

assignment=json.loads((ROOT/'inputs'/FOLDER.name/'assignment.json').read_text())
manifest=json.loads((FOLDER/'draft-execution-manifest.json').read_text())
print('input has law_record:', 'law_record' in assignment, flush=True)
print('input has law:', 'law' in assignment, flush=True)
print(validate(FOLDER,assignment,manifest))
