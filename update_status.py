import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'runtime/main-pipeline-v1/scenario_pipeline'))
from worker_exchange.updates import state
print(json.dumps(state(Path(__file__).resolve().parent),indent=2))
