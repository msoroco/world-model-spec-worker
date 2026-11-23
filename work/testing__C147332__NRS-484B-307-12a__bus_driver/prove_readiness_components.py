"""Check exact compatibility, physical and delivery CPU receipts with pinned runtime."""
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
from worker_exchange.candidate_constructions import validate as validate_candidates
from worker_exchange.physical_preparation import validate as validate_physical
from worker_exchange.delivery_handoff import validate_case
from worker_exchange.execution_manifest import validate as validate_manifest

manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
validate_manifest(REPO, ROOT.name)
assert check_receipts(REPO, ROOT, manifest)
for entry in manifest['cases']:
    assert validate_candidates(ROOT, entry, 'NRS-484B-307-12a', 'C147332',
                               required=True, require_alternate=True, candidate_count=2)['fallbacks'] == ['fallback1']
    validate_physical(REPO, ROOT, entry)
    validate_case(ROOT, entry, expected_sets=('full-test',))
    print(entry['case_id'], 'compatibility, physical CPU and delivery audit receipts verified')
print('four exact cases verified; Native physical acceptance unclaimed')
