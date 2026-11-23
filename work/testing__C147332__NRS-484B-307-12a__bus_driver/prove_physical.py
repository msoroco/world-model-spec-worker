"""Verify four exact synthetic physical CPU receipts with the pinned gate."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
if not output_root.is_relative_to((REPO / '.runtime-work').resolve()):
    raise ValueError('SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work')
sys.path.insert(0, str((REPO / 'runtime/scenario_pipeline').resolve()))
from worker_exchange.physical_preparation import validate

manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
for entry in manifest['cases']:
    validate(REPO, ROOT, entry)
    print(entry['case_id'], 'three physical outcomes and lifecycle verified')
print('all four exact physical CPU receipts verified')
