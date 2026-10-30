import sys,json
from pathlib import Path
root=Path(__file__).resolve().parent
batch=json.loads((root/'batch.json').read_text())
sys.path.insert(0,str(root/batch['runtime']['root']/'scenario_pipeline'))
from worker_exchange.updates import state
print(json.dumps(state(root),indent=2))
