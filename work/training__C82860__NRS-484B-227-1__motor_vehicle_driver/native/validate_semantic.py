import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path('runtime').resolve()))
sys.path.insert(0, str(Path('runtime/scenario_pipeline').resolve()))
from scenario_pipeline.worker_exchange.semantic_delivery import validate
p = Path('work/training__C82860__NRS-484B-227-1__motor_vehicle_driver')
a = json.loads(Path('inputs/training__C82860__NRS-484B-227-1__motor_vehicle_driver/assignment.json').read_text())
m = json.loads((p / 'draft-native-manifest.json').read_text())
print(json.dumps(validate(p, a, m), sort_keys=True))
