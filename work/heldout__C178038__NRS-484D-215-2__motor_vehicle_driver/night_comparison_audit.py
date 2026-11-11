"""Compare source-bound nighttime headlamp diagnostics without legal labels."""

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.package_compatibility import check_receipts


CASES = ('night_299_upper', 'night_299_other', 'night_300_upper', 'night_301_upper')


def _case_record(receipt):
    if not receipt.get('passed') or receipt.get('candidate_id') != 'primary':
        raise ValueError('Comparison needs passed primary receipt')
    item = receipt['measurement_examples']['headlamp_following_observation']
    value = item['value']
    rows = value['observations']
    if len(rows) != 9 or not value['lighting_time_applies']:
        raise ValueError('Nighttime source observations incomplete')
    if any(not row['following_geometry'] or not row['low_beam_readback']
           for row in rows):
        raise ValueError('Original following or low-beam source differs')
    return item['sources'], rows


def compare(records):
    if set(records) != set(CASES):
        raise ValueError('Exact four-case comparison incomplete')
    parsed = {suffix: _case_record(records[suffix]) for suffix in CASES}
    for suffix, expected_gap, expected_upper in (
        ('night_299_upper', 299, True),
        ('night_299_other', 299, False),
        ('night_300_upper', 300, True),
        ('night_301_upper', 301, True),
    ):
        sources, rows = parsed[suffix]
        if any(abs(row['surface_gap_ft'] - expected_gap) > 1e-5 or
               row['uppermost_distribution_readback'] is not expected_upper or
               row['below_300ft'] is not (expected_gap < 300) or
               row['at_300ft'] is not (expected_gap == 300)
               for row in rows):
            raise ValueError('Measured gap or beam comparison differs: ' + suffix)
    upper_sources, upper_rows = parsed['night_299_upper']
    other_sources, other_rows = parsed['night_299_other']
    for name in upper_sources:
        if name != 'headlamp_readbacks.jsonl' and upper_sources[name] != other_sources[name]:
            raise ValueError('Beam comparison changed another original source: ' + name)
    if upper_sources['headlamp_readbacks.jsonl'] == other_sources['headlamp_readbacks.jsonl']:
        raise ValueError('Beam comparison did not change lamp source')
    for suffix in ('night_300_upper', 'night_301_upper'):
        sources, rows = parsed[suffix]
        for name in upper_sources:
            if name != 'following_footprints.jsonl' and upper_sources[name] != sources[name]:
                raise ValueError('Distance comparison changed another source: ' + name)
        if upper_sources['following_footprints.jsonl'] == sources['following_footprints.jsonl']:
            raise ValueError('Distance comparison did not change body source')
        if [r['frame'] for r in rows] != [r['frame'] for r in upper_rows]:
            raise ValueError('Comparison frame identities differ')
    return {'format': 'worker-night-headlamp-comparison-audit',
            'passed': True, 'scope': 'synthetic source-bound software comparison only',
            'cases': list(CASES),
            'measurements_ft': {suffix: parsed[suffix][1][0]['surface_gap_ft']
                                for suffix in CASES},
            'legal_judgment': None, 'physical_outcome_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((HERE / 'night-all-fallback-manifest.json').read_text())
    check_receipts(ROOT, HERE, manifest)
    records = {}
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[1]
        records[suffix] = json.loads((HERE / entry['compatibility']['receipt']).read_text())
    if args.negative:
        records = deepcopy(records)
        records['night_300_upper']['measurement_examples']['headlamp_following_observation']['value']['observations'][0]['surface_gap_ft'] = 299
    report = compare(records)
    report['manifest_sha256'] = sha256((HERE / 'night-all-fallback-manifest.json').read_bytes()).hexdigest()
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
