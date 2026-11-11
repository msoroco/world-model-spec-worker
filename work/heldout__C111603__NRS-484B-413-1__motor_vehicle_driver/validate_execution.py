"""Run the pinned aggregate execution-manifest validator."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.execution_manifest import validate

result = validate(ROOT, HERE.name)
print('PINNED_EXECUTION_MANIFEST_PASS', len(result['cases']))
