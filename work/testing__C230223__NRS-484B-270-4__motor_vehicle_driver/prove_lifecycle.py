"""Synthetic saved-only capture lifecycle protocol check."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cycle_lane_intersection import ASSIGNMENT

EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--attempt', type=Path, required=True)
    p.add_argument('--saved-receipt', type=Path, required=True)
    args = p.parse_args()
    if args.case not in {c['case_id'] for c in json.loads((Path(__file__).resolve().parent / 'case-plan.json').read_text())['cases']}:
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
