"""Audit the exact fixed conditions for opposite straight versus intended left."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
STRAIGHT = ROOT / 'cases/source_verified_opposite_straight'
LEFT = ROOT / 'cases/source_verified_opposite_intends_left'
STRAIGHT_ATTEMPT = REPO / '.runtime-work/c125714-opposite-straight-compat-v1'
LEFT_ATTEMPT = REPO / '.runtime-work/c125714-opposite-intends-compat-v1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(straight=STRAIGHT_ATTEMPT, left=LEFT_ATTEMPT):
    fixed = ['road_geometry.json', 'road.xodr', 'crossing_history.jsonl',
             'controller_history.jsonl', 'capture/evidence.jsonl',
             'video_frames.jsonl', 'overview.mkv', 'approach.mkv',
             'reference_corner.mkv', 'driver_reference.mkv']
    same = {}
    for name in fixed:
        a, b = straight / name, left / name
        if not a.is_file() or not b.is_file() or digest(a) != digest(b):
            raise ValueError('Fixed source differs or is missing: ' + name)
        same[name] = digest(a)
    a = json.loads((straight / 'turn_intent.json').read_text())
    b = json.loads((left / 'turn_intent.json').read_text())
    if ({k: v for k, v in a.items() if k != 'intended_maneuver'} !=
        {k: v for k, v in b.items() if k != 'intended_maneuver'} or
        a.get('intended_maneuver') != 'straight' or
        b.get('intended_maneuver') != 'left' or
        a.get('actor_id') != 102):
        raise ValueError('Intention difference is not isolated')
    for folder, expected in ((STRAIGHT, 'straight'), (LEFT, 'left')):
        diagnostic = json.loads((folder / 'diagnostic.json').read_text())
        construction = json.loads((folder / 'construction.json').read_text())
        config = json.loads(next(f['content'] for f in construction['files']
                                 if f['path'] == 'config.json'))
        if config['other_intent'] != expected or json.loads(diagnostic['files']['turn_intent.json'])['intended_maneuver'] != expected:
            raise ValueError('Authored intention is inconsistent: ' + expected)
    results = []
    for attempt, expected in ((straight, 'straight'), (left, 'left')):
        receipt = json.loads((attempt / 'compatibility.json').read_text())
        if receipt.get('passed') is not True:
            raise ValueError('Compatibility receipt not passed: ' + expected)
        report = json.loads((attempt / 'analysis-report.json').read_text())
        row = report.get('measurements', {}).get('opposite_approach', {}).get('value', {})
        if row.get('intended_maneuver') != expected or row.get('observed_heading_range_deg') != [180, 180]:
            raise ValueError('Measured intention or original heading changed: ' + expected)
        results.append({'intention': expected, 'measured': True})
    return {'format': 'worker-opposite-intention-comparison', 'fixed_sources': same,
            'declared_difference': 'authored intended maneuver only',
            'results': results, 'legal_applicability': 'unresolved',
            'physical_acceptance_claimed': False}


def main():
    receipt = audit()
    (LEFT / 'comparison-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'fixed_sources': len(receipt['fixed_sources']),
                      'intentions': [row['intention'] for row in receipt['results']]}))


if __name__ == '__main__':
    main()
