"""Positive and negative independent qualifier delivery/comparison proofs."""
import hashlib
import json
from pathlib import Path
import shutil

from qualifier_delivery_audit import audit


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
BASE = ROOT / '.runtime-work/c229397-saved-attempt-controlled_2-v2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    reports = {}
    altered = ROOT / '.runtime-work/c229397-qualifier-altered-baseline-v3'
    if altered.exists():
        raise ValueError('Retain prior altered baseline')
    altered.mkdir()
    inventory = json.loads((BASE / 'crosswalk-inventory.json').read_text())
    inventory['crosswalk_rect_xyxy_m'] = [1, 4, -6.5, 0]
    (altered / 'crosswalk-inventory.json').write_text(json.dumps(inventory) + '\n')
    shutil.copyfile(BASE / 'crosswalk-source-review.json', altered / 'crosswalk-source-review.json')
    for suffix, stem in (('traffic_conflict_near', 'traffic'),
                         ('law_compliance_near', 'law'),
                         ('police_direction_near', 'officer'),
                         ('device_direction_near', 'device')):
        attempt = ROOT / ('.runtime-work/c229397-qualifier-' + stem + '-recorded-positive-v6')
        processing = ROOT / ('.runtime-work/c229397-qualifier-' + stem + '-saved-positive-v5/v0001/processing.json')
        case = ASSIGNMENT + '__' + suffix
        result = audit(case, attempt, processing, BASE, diagnostic=True)
        receipt = HERE / 'proofs' / 'qualifiers' / stem / 'delivery-audit.json'
        receipt.write_text(json.dumps(result, indent=2) + '\n')
        if result['finding'] != 'unresolved' or result['legal_verdict'] is not None:
            raise ValueError('Qualifier audit crossed legal acceptance boundary')
        try:
            audit(case, attempt, processing, altered, diagnostic=True)
        except ValueError as error:
            if str(error) != 'Controlled crosswalk context differs':
                raise
        else:
            raise ValueError('Altered controlled baseline accepted')
        try:
            audit(case, attempt, processing, BASE, diagnostic=False)
        except ValueError:
            pass
        else:
            raise ValueError('Synthetic qualifier passed original-mode audit')
        reports[suffix] = {'receipt_sha256': sha(receipt),
                           'positive_diagnostic': True,
                           'altered_baseline_rejected': True,
                           'synthetic_original_rejected': True}
    print(json.dumps({'passed': True, 'diagnostic_fixture': True,
                      'cases': reports, 'physical_acceptance_claimed': False,
                      'legal_verdict_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
