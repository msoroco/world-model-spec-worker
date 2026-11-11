"""Independently validate first exact case and three candidate CPU receipts."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.candidate_constructions import validate as validate_candidates
from worker_exchange.delivery_handoff import validate_case
from worker_exchange.package_compatibility import check_receipts

manifest = json.loads((ROOT / 'vehicle-indicator-manifest.json').read_text())
entry = manifest['cases'][0]
validate_candidates(ROOT, entry, 'NRS-484B-413-1', 'C111603',
                    required=True, require_alternate=True, candidate_count=4)
validate_case(ROOT, entry, expected_sets=('held-out',))
check_receipts(REPO, ROOT, manifest)
saved = json.loads((ROOT / 'vehicle-indicator-saved-receipt.json').read_text())
assert saved['passed'] and saved['originals_preserved'] and not saved['missing_evidence']
assert not saved['physical_acceptance_claimed'] and not saved['legal_acceptance_claimed']
print('Exact vehicle indicator primary, three fallbacks, saved and independent audit contracts pass')
