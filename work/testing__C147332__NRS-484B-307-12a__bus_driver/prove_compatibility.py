"""Verify all exact pinned compatibility receipts against current constructions."""
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
from worker_exchange.package_compatibility import check_receipts
from worker_exchange.candidate_constructions import validate

manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
assert check_receipts(REPO, ROOT, manifest)
for entry in manifest['cases']:
    value = validate(ROOT, entry, 'NRS-484B-307-12a', 'C147332',
                     required=True, require_alternate=True, candidate_count=2)
    assert value['fallbacks'] == ['fallback1']
    print(entry['case_id'], 'primary and fallback receipts verified')
print('all eight exact compatibility receipts verified')
