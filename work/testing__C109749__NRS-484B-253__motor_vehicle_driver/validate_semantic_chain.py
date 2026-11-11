"""Run the pinned full semantic-stage source and case bindings validator."""
import json
import sys
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
sys.path.insert(0,str(repo/'runtime/scenario_pipeline'))
sys.path.insert(1,str(repo/'runtime/python'))
from worker_exchange.semantic_delivery import validate

assignment = json.loads((repo/'inputs'/folder.name/'assignment.json').read_text())
manifest = json.loads((folder/'execution-manifest.json').read_text())
print(json.dumps(validate(folder,assignment,manifest),sort_keys=True))
