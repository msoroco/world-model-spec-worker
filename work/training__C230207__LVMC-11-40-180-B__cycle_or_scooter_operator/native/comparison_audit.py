"""Independent selected signed-road comparison of 600-frame synthetic probes."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
AID = HERE.name
HELD = ('road_sha256', 'governed_x_interval_m', 'street_y_m', 'cameras',
        'capture_frames', 'rate_hz', 'actor', 'law_id', 'cell_id')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(negative=False):
    configs = {}
    results = {}
    sources = {}
    for suffix in ('witness_1', 'witness_2'):
        construction_path = HERE / ('construction.json' if suffix == 'witness_1'
                                    else 'cases/witness_2/construction.json')
        construction = json.loads(construction_path.read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        if construction['case_id'] != AID + '__' + suffix or config['capture_frames'] != 600:
            raise ValueError('Selected full-length construction differs')
        configs[suffix] = config
        sources[suffix] = sha(construction_path)
        receipt_path = HERE / 'physical' / suffix / 'complete_motion-result.json'
        physical = json.loads(receipt_path.read_text())
        if (physical['case_id'] != construction['case_id'] or
                physical['diagnostic_fixture'] is not True or
                physical['physical_checks']['maneuver']['status'] != 'met'):
            raise ValueError('Synthetic physical comparison source differs')
        results[suffix] = physical['realized_observables']['signed_roadway_riding_frames']
    if negative:
        configs['witness_2']['governed_x_interval_m'] = [0, 10]
    if any(configs['witness_1'][key] != configs['witness_2'][key] for key in HELD):
        raise ValueError('Signed-road comparison changed held condition')
    if (configs['witness_1']['route_kind'] != 'outside' or
            configs['witness_2']['route_kind'] != 'enter' or
            results != {'witness_1': 0, 'witness_2': 400}):
        raise ValueError('Selected signed-road access contrast differs')
    return {'format': 'c230207-comparison-audit-v1',
            'comparison_id': AID + '__witness_comparison', 'passed': True,
            'case_ids': [AID + '__witness_1', AID + '__witness_2'],
            'construction_sha256': sources, 'held_fields': HELD,
            'signed_roadway_riding_frames': results,
            'full_length_synthetic_frames': 600,
            'original_native_executed': False,
            'physical_or_legal_acceptance': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative-selftest', action='store_true')
    arguments = parser.parse_args()
    print(json.dumps(audit(arguments.negative_selftest), sort_keys=True))
