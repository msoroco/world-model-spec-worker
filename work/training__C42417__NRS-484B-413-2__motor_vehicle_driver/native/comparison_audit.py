"""Independent source-hash and fixed-condition distance comparison audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from measure_observed import CASE_PREFIX, measure


SOURCES = ('native_samples.jsonl', 'video_frames.jsonl',
           'body_history.jsonl', 'road_geometry.json', 'control_context.json')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(left_attempt: Path, right_attempt: Path, left_receipt: Path,
          right_receipt: Path, *, middle_attempt=None, middle_receipt=None,
          allow_fixture: bool = False) -> dict:
    if (middle_attempt is None) != (middle_receipt is None):
        raise ValueError('At-threshold case needs its source and receipt')
    cases = [CASE_PREFIX + 'a', CASE_PREFIX + 'b']
    attempts = [Path(left_attempt), Path(right_attempt)]
    receipts = [Path(left_receipt), Path(right_receipt)]
    if middle_attempt is not None:
        cases.insert(1, CASE_PREFIX + 'c')
        attempts.insert(1, Path(middle_attempt))
        receipts.insert(1, Path(middle_receipt))
    measured = []
    for case, attempt, receipt_path in zip(cases, attempts, receipts):
        if not receipt_path.is_file():
            raise ValueError('Missing saved measurement receipt')
        receipt = json.loads(receipt_path.read_text())
        if receipt.get('case_id') != case or receipt.get('format') != 'c42417-source-joined-saved-distance-v1':
            raise ValueError('Comparison case/receipt identity differs')
        if receipt.get('requested_signal_distance_m') != {'a':40,'b':20,'c':30.48}[case[-1]]:
            raise ValueError('Deliberate signal-distance request differs')
        for name in SOURCES:
            source = attempt / name
            if not source.is_file() or receipt.get('source_hashes', {}).get(name) != sha(source):
                raise ValueError('Missing or stale original comparison source: ' + name)
        recomputed = measure(attempt / 'native_samples.jsonl', case,
                             allow_fixture=allow_fixture)
        if recomputed != receipt.get('measurement') or \
                recomputed['continuous_observed_signal_distance_m'] != receipt.get('measured_signal_distance_m'):
            raise ValueError('Saved signal measurement differs from source')
        if not allow_fixture and not recomputed['original_native_observed']:
            raise ValueError('Original Native comparison evidence required')
        config_path = attempt / 'config.json'
        if not config_path.is_file():
            raise ValueError('Missing exact comparison config')
        config = json.loads(config_path.read_text())
        fixed = (config.get('law_id'), config.get('cell_id'), config.get('actor'),
                 config.get('layout'), config.get('maneuver'), config.get('precipitation'),
                 config.get('rate_hz'), config.get('duration_s'),
                 tuple((camera.get('name'), camera.get('width'), camera.get('height'),
                        camera.get('fps')) for camera in config.get('cameras', [])))
        if fixed[:8] != ('NRS-484B-413-2', 'C42417', 'motor_vehicle_driver',
                         'business_district', 'right_turn', 'rain', 20, 30):
            raise ValueError('Comparison fixed conditions changed')
        if fixed[8] != (('overview', 1920, 1080, 20),
                        ('approach', 1280, 720, 20),
                        ('reference_corner', 1280, 720, 20),
                        ('driver_reference', 1280, 720, 20)):
            raise ValueError('Comparison fixed camera plan changed')
        measured.append((fixed, recomputed['continuous_observed_signal_distance_m'],
                         {name: sha(attempt / name) for name in SOURCES}))
    if any(row[0] != measured[0][0] for row in measured[1:]):
        raise ValueError('Comparison fixed conditions changed')
    if not all(measured[i][1] > measured[i+1][1] for i in range(len(measured)-1)):
        raise ValueError('Measured signal-distance ordering absent')
    return {'format': 'c42417-independent-comparison-audit-v1',
            'comparison_id': CASE_PREFIX[:-len('condition_')] + 'comparison',
            'case_ids': list(cases), 'fixed_conditions': measured[0][0],
            'measured_distances_m': [row[1] for row in measured],
            'source_hashes': [row[2] for row in measured],
            'diagnostic_fixture': allow_fixture,
            'physical_acceptance_claimed': False, 'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--left-attempt', type=Path, required=True)
    parser.add_argument('--right-attempt', type=Path, required=True)
    parser.add_argument('--left-receipt', type=Path, required=True)
    parser.add_argument('--right-receipt', type=Path, required=True)
    parser.add_argument('--middle-attempt', type=Path)
    parser.add_argument('--middle-receipt', type=Path)
    parser.add_argument('--allow-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.left_attempt, args.right_attempt,
                           args.left_receipt, args.right_receipt,
                           middle_attempt=args.middle_attempt,
                           middle_receipt=args.middle_receipt,
                           allow_fixture=args.allow_fixture), indent=2))
