"""Compare the finite approach-position grid without assigning a legal cutoff."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile

from turn_comparison_audit import audit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main():
    proof_path = ROOT / 'candidate-proofs.json'
    proofs = json.loads(proof_path.read_text())
    rows = []
    source_hashes = []
    for index in range(3):
        case_id = ROOT.name + '__approach_practicability_grid-' + str(index).zfill(4)
        proof = next(p for p in proofs if p['case_id'] == case_id and p['candidate_id'] == 'primary')
        receipt = proof['compatibility_receipt']
        if not receipt['passed'] or 'negative_case_source' not in receipt['checks']:
            raise ValueError('grid source compatibility is unproved: ' + case_id)
        item = receipt['measurement_examples']['turn_geometry']
        for source in ('road_geometry.json', 'body_footprints.json'):
            if source not in item['sources'] or not item['sources'][source]:
                raise ValueError('grid original source hash missing: ' + source)
        rows.append(item['value'])
        source_hashes.append({source: item['sources'][source] for source in
                              ('road_geometry.json', 'body_footprints.json')})
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c109705-grid-audit-') as temporary:
        paths = []
        for index, row in enumerate(rows):
            path = Path(temporary) / f'{index}.json'
            path.write_text(json.dumps(row) + '\n')
            paths.append(path)
        comparisons = [audit([paths[a], paths[b]], 'approach_curb_position')
                       for a, b in ((0, 1), (0, 2), (1, 2))]
        tampered = deepcopy(rows[1])
        tampered['departure_centerline_min_signed_m'] -= .2
        paths[1].write_text(json.dumps(tampered) + '\n')
        try:
            audit(paths[:2], 'approach_curb_position')
        except ValueError as error:
            if 'held departure position' not in str(error):
                raise
        else:
            raise ValueError('changed held departure escaped grid audit')
    report = {'case_ids': [ROOT.name + '__approach_practicability_grid-' + str(i).zfill(4)
                           for i in range(3)],
              'candidate_id': 'primary',
              'candidate_proofs_sha256': sha256(proof_path.read_bytes()).hexdigest(),
              'source_hashes': source_hashes,
              'comparisons': comparisons,
              'negative_changed_held_departure_rejected': True,
              'legal_conclusion': None, 'physical_acceptance_claimed': False}
    (ROOT / 'practicability-grid-proof.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Three source-bound grid comparisons and changed-held-condition rejection passed')


if __name__ == '__main__':
    main()
