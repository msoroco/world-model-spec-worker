"""Check all nine exact source-bound compatibility receipts."""

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.package_compatibility import check_receipts

manifest = json.loads((HERE / 'execution-manifest.json').read_text())
check_receipts(ROOT, HERE, manifest)
print('PINNED_COMPATIBILITY_PASS', len(manifest['cases']))
