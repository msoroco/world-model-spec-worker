"""Audit synthetic day and shoulder controls against the nighttime source."""

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


def _record(entry, folder):
    proof = json.loads((HERE / entry['compatibility']['receipt']).read_text())
    measurement = proof['measurement_examples']['headlamp_following_observation']
    source = json.loads((HERE / folder / (entry['case_id'].rsplit('__', 1)[1] + '-diagnostic-input.json')).read_text())
    return measurement, source['files']


def compare(records):
    if set(records) != {'night', 'day', 'shoulder'}:
        raise ValueError('Context comparison needs night, day and shoulder')
    for name, (measurement, files) in records.items():
        value = measurement['value']
        rows = value['observations']
        if len(rows) != 9 or any(abs(row['surface_gap_ft'] - 299) > 1e-5 or
                                 not row['following_geometry'] or
                                 not row['uppermost_distribution_readback']
                                 for row in rows):
            raise ValueError('299 ft upper-beam context geometry differs: ' + name)
        for source_name in ('lighting_context.json', 'roadway_environment.jsonl'):
            if measurement['sources'][source_name] != sha256(files[source_name].encode()).hexdigest():
                raise ValueError('Context source hash differs: ' + name)
    night, day, shoulder = (records[name] for name in ('night', 'day', 'shoulder'))
    if (night[0]['value']['lighting_time_applies'] is not True or
            day[0]['value']['lighting_time_applies'] is not False or
            shoulder[0]['value']['lighting_time_applies'] is not True):
        raise ValueError('Authored lighting-time premise differs')
    fixed = ('following_footprints.jsonl', 'headlamp_readbacks.jsonl',
             'trace.jsonl', 'video_frames.jsonl')
    for key in fixed:
        if len({records[name][0]['sources'][key] for name in records}) != 1:
            raise ValueError('Context comparison changed fixed source: ' + key)
    if night[0]['sources']['lighting_context.json'] != shoulder[0]['sources']['lighting_context.json']:
        raise ValueError('Shoulder comparison changed lighting-time source')
    for name, expected_lane, expected_sun in (
        ('night', 'Driving', -10), ('day', 'Driving', 45),
        ('shoulder', 'Shoulder', -10),
    ):
        rows = [json.loads(line) for line in records[name][1]['roadway_environment.jsonl'].splitlines()]
        if len(rows) != 9 or any(row['lane_type_readback'] != expected_lane or
                                 row['sun_altitude_angle_deg'] != expected_sun or
                                 not row['waypoint_present'] for row in rows):
            raise ValueError('Roadway/sun original-shaped source differs: ' + name)
    return {'format': 'worker-context-comparison-audit', 'passed': True,
            'scope': 'synthetic source-bound software comparison only',
            'lighting_time': {'night': True, 'day': False, 'shoulder': True},
            'roadway': {'night': 'Driving', 'day': 'Driving', 'shoulder': 'Shoulder'},
            'physical_outcome_claimed': False, 'legal_judgment': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    night_manifest = json.loads((HERE / 'night-all-fallback-manifest.json').read_text())
    context_manifest = json.loads((HERE / 'context-execution-manifest.json').read_text())
    check_receipts(ROOT, HERE, night_manifest)
    check_receipts(ROOT, HERE, context_manifest)
    entries = {'night': (night_manifest['cases'][0], 'night-probes'),
               'day': (context_manifest['cases'][0], 'context-probes'),
               'shoulder': (context_manifest['cases'][1], 'context-probes')}
    records = {name: _record(*entry) for name, entry in entries.items()}
    if args.negative:
        records = deepcopy(records)
        records['shoulder'][0]['value']['lighting_time_applies'] = False
    print(json.dumps(compare(records), indent=2))


if __name__ == '__main__':
    main()
