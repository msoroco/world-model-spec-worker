"""Verify all six source-bound physical preparation receipts on the pinned runtime."""
import hashlib
from pathlib import Path

from worker_exchange.physical_preparation import validate

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
for suffix in ('dry_open_traffic', 'wet_same_traffic', 'dense_traffic',
               'narrow_same_traffic', 'low_visibility', 'ice_or_snow'):
    construction = ROOT / ('construction.json' if suffix == 'dry_open_traffic' else
                           'cases/' + suffix + '-construction.json')
    receipt = 'cases/' + suffix + '-physical-preparation.json'
    entry = {'case_id': 'testing__C179789__NRS-484B-600-1a__motor_vehicle_driver__' + suffix,
             'construction_sha256': hashlib.sha256(construction.read_bytes()).hexdigest(),
             'physical_preparation': {
                 'receipt': receipt,
                 'sha256': hashlib.sha256((ROOT / receipt).read_bytes()).hexdigest()}}
    validate(REPO, ROOT, entry)
    print(entry['case_id'], 'physical preparation passed')
