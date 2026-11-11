"""Check every exact delivery audit contract with the pinned validator."""

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.delivery_handoff import validate_case

manifest = json.loads((HERE / 'execution-manifest.json').read_text())
for entry in manifest['cases']:
    validate_case(HERE, entry, ['held-out'])
print('PINNED_DELIVERY_CASES_PASS', len(manifest['cases']))
