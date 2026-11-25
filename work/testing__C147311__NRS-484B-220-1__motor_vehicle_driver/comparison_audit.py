"""Independent saved-source one-way lane/direction comparison audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from one_way_direction import CASES

ASSIGNMENT = 'testing__C147311__NRS-484B-220-1__motor_vehicle_driver'
FIXED = ('highway', 'vehicle', 'driver_control', 'lane_inventory',
         'one_way_designation', 'sign_authority', 'sign_message',
         'sign_orientation', 'sign_placement', 'sign_governance')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_case(attempt: Path, processing: Path) -> dict:
    receipt_path = processing / 'processing-receipt.json'
    measurement_path = processing / 'measurement.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    measurement = json.loads(measurement_path.read_text(encoding='utf-8'))
    if sha(measurement_path) != receipt['measurement_sha256'] or receipt['legal_verdict_claimed'] is not False:
        raise ValueError('saved direction receipt changed or claimed legal verdict')
    case_id = receipt['case_id']
    suffix = case_id.removeprefix(ASSIGNMENT + '__')
    case = next((c for c in CASES if c.name == suffix), None)
    if case is None or case_id != ASSIGNMENT + '__' + suffix or measurement['case_id'] != suffix:
        raise ValueError('comparison case identity mismatch')
    diagnostic = receipt['source_kind'] == 'synthetic_software_fixture'
    source_path = attempt / ('diagnostic-scene.json' if diagnostic else 'site-source.json')
    if sha(source_path) != receipt['scene_sha256']:
        raise ValueError('comparison source scene hash changed')
    source = json.loads(source_path.read_text(encoding='utf-8'))
    scene = source if diagnostic else source['scene']
    if scene['lane'] != case.lane or scene['direction'] != case.direction:
        raise ValueError('comparison source setup differs from exact case')
    if measurement['actual_direction'] != case.direction or measurement['frame_count'] != 900:
        raise ValueError('realized direction or duration differs from exact case')
    return {'case_id': case_id, 'case': case, 'scene': scene, 'receipt': receipt,
            'measurement_sha256': sha(measurement_path), 'diagnostic': diagnostic}


def audit(left_attempt: Path, left_processing: Path,
          right_attempt: Path, right_processing: Path,
          comparison_id: str, allow_diagnostic=False) -> dict:
    left = read_case(left_attempt, left_processing)
    right = read_case(right_attempt, right_processing)
    if left['diagnostic'] != right['diagnostic'] or (left['diagnostic'] and not allow_diagnostic):
        raise ValueError('original comparison sources required')
    plan = json.loads((Path(__file__).resolve().parent / 'case-plan.json').read_text(encoding='utf-8'))
    matches = [row for row in plan['comparisons'] if row['comparison_id'] == comparison_id]
    if len(matches) != 1 or matches[0]['case_ids'] != [left['case_id'], right['case_id']]:
        raise ValueError('selected comparison pair differs')
    for field in FIXED:
        key = field + '_source_sha256'
        if left['scene'][key] != right['scene'][key]:
            raise ValueError('fixed source context differs: ' + field)
    if comparison_id.startswith('actual_direction_'):
        if left['case'].lane != right['case'].lane or left['case'].direction == right['case'].direction:
            raise ValueError('actual-direction variable not isolated')
    else:
        if left['case'].direction != right['case'].direction or left['case'].lane == right['case'].lane:
            raise ValueError('lane variable not isolated')
    return {'format': 'c147311-comparison-audit-v1', 'comparison_id': comparison_id,
            'case_ids': matches[0]['case_ids'],
            'measurement_sha256': [left['measurement_sha256'], right['measurement_sha256']],
            'fixed_source_hashes': {field: left['scene'][field + '_source_sha256'] for field in FIXED},
            'source_kind': 'synthetic_software_fixture' if left['diagnostic'] else 'original_native_attempt',
            'actual_directions': [left['case'].direction, right['case'].direction],
            'lanes': [left['case'].lane, right['case'].lane],
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--left-attempt', type=Path, required=True)
    p.add_argument('--left-processing', type=Path, required=True)
    p.add_argument('--right-attempt', type=Path, required=True)
    p.add_argument('--right-processing', type=Path, required=True)
    p.add_argument('--comparison', required=True)
    p.add_argument('--allow-diagnostic', action='store_true')
    args = p.parse_args()
    print(json.dumps(audit(args.left_attempt, args.left_processing,
                           args.right_attempt, args.right_processing,
                           args.comparison, args.allow_diagnostic), sort_keys=True))


if __name__ == '__main__':
    main()
