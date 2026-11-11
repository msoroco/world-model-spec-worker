"""Validate exact narrow-case CPU construction, receipts, saved path and audit."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.candidate_constructions import validate as validate_candidates
from worker_exchange.delivery_handoff import validate_case
from worker_exchange.package_compatibility import check_receipts

manifest = json.loads((ROOT / 'clearance-narrow-manifest.json').read_text())
entry = manifest['cases'][0]
validate_candidates(ROOT, entry, 'NRS-484B-413-1', 'C111603',
                    required=True, require_alternate=True, candidate_count=4)
validate_case(ROOT, entry, expected_sets=('held-out',))
check_receipts(REPO, ROOT, manifest)
saved = json.loads((ROOT / 'clearance-narrow-saved-receipt.json').read_text())
assert saved['passed'] and saved['originals_preserved'] and not saved['missing_evidence']
assert not saved['physical_acceptance_claimed'] and not saved['legal_acceptance_claimed']
audit = json.loads((ROOT / 'clearance-narrow-audit.json').read_text())
assert audit['source_integrity_passed'] and audit['controlled_pair_passed']
assert audit['video_decode_count'] == 4 and not audit['physical_safety_verified']
print('Narrow clearance exact primary, fallbacks, saved and comparison contracts pass')
