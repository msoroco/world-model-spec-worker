"""Prove stage drafts using an in-memory law_record alias only."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
FOLDER=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate

assignment=json.loads((ROOT/'inputs'/FOLDER.name/'assignment.json').read_text())
assignment['law']=assignment['law_record']
manifest=json.loads((FOLDER/'draft-execution-manifest.json').read_text())
print(json.dumps(validate(FOLDER,assignment,manifest),indent=2))
