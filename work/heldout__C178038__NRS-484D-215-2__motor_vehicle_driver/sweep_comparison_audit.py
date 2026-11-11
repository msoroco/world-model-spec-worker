"""Audit exact synthetic illumination-distance coverage, without a legal label."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.package_compatibility import check_receipts


def audit(negative=False):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    check_receipts(ROOT, HERE, manifest)
    spec = next(s for s in json.loads((HERE / 'proposals/cases.json').read_text())['sweep_specs']
                if s['status'] == 'complete')
    selected = {e['case_id']: e for e in manifest['cases'] if e['case_id'] in spec['selection_order']}
    if set(selected) != set(spec['selection_order']) or spec['planned_case_count'] != 3:
        raise ValueError('Frozen illumination sweep selection incomplete')
    points = []
    stable = None
    for case_id in spec['selection_order']:
        entry = selected[case_id]
        receipt_path = HERE / entry['compatibility']['receipt']
        if sha256(receipt_path.read_bytes()).hexdigest() != entry['compatibility']['sha256']:
            raise ValueError('Sweep compatibility receipt stale')
        receipt = json.loads(receipt_path.read_text())
        item = receipt['measurement_examples']['headlamp_following_observation']
        rows = item['value']['observations']
        expected = next(c['sweep_point']['requested_gap_ft'] for c in
                        json.loads((HERE / 'proposals/cases.json').read_text())['cases']
                        if c['case_id'] == case_id)
        if negative and case_id == spec['selection_order'][-1]:
            expected += 1
        if len(rows) != 9 or any(abs(row['surface_gap_ft'] - expected) > 1e-5 or
                                  row['uppermost_distribution_readback'] is not False or
                                  row['following_geometry'] is not True for row in rows):
            raise ValueError('Sweep realized body gap or low-beam readback differs')
        sources = item['sources']
        other = {name: value for name, value in sources.items()
                 if name != 'following_footprints.jsonl'}
        if stable is None:
            stable = other
        elif other != stable:
            raise ValueError('Sweep changed a source other than body geometry')
        points.append({'case_id': case_id, 'requested_gap_ft': expected,
                       'measured_gap_ft': rows[0]['surface_gap_ft'],
                       'original_body_source_sha256': sources['following_footprints.jsonl']})
    return {'format': 'worker-illumination-sweep-comparison-audit', 'passed': True,
            'scope': 'synthetic source-bound CPU diagnostic',
            'sweep_spec_version': spec['spec_version'], 'points': points,
            'legal_judgment': None, 'physical_outcome_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.negative), indent=2))
