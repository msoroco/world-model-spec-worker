"""Synthetic saved-only capture lifecycle protocol check."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from one_way_direction import CASES

ASSIGNMENT = 'testing__C147311__NRS-484B-220-1__motor_vehicle_driver'
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--attempt', type=Path, required=True)
    p.add_argument('--saved-receipt', type=Path, required=True)
    args = p.parse_args()
    if args.case not in {ASSIGNMENT + '__' + c.name for c in CASES}:
        raise ValueError('exact case required')
    provenance = json.loads((args.attempt / 'acquisition-provenance.json').read_text(encoding='utf-8'))
    saved = json.loads(args.saved_receipt.read_text(encoding='utf-8'))
    if (provenance.get('provenance_kind') != 'synthetic_fixture' or
            provenance.get('diagnostic_fixture') is not True or
            saved.get('case_id') != args.case or not saved.get('passed') or
            not saved.get('recorded_only') or not saved.get('originals_preserved')):
        raise ValueError('synthetic saved-only lifecycle source invalid')
    print(json.dumps({'case_id': args.case, 'scope': 'synthetic lifecycle protocol only',
                      'events': EVENTS, 'exit_code': 0,
                      'original_owner_release_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
