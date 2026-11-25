"""Classify synthetic motion fixtures without making an original or legal claim."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from red_left_measurement import measure_exact


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(case: str, packet: Path, history: Path, plan: Path) -> dict:
    packet, history, plan = Path(packet), Path(history), Path(plan)
    sources = {'plan': sha(plan)}
    if not packet.is_file() or not history.is_file():
        status, motion, reason = 'unverified', None, 'original geometry or history missing'
    else:
        measured = measure_exact(packet, history, case, plan)
        sources.update(site_packet=sha(packet), history=sha(history))
        motion = measured
        status = 'met' if measured['first_entry_frame'] is not None else 'not_met'
        reason = 'measured full-body crossing of reviewed stop reference'
    return {'case_id': case, 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False,
            'maneuver_completed': status == 'met',
            'physical_checks': {'maneuver': {'status': status,
                                            'method': 'source-bound full-body entry measurement',
                                            'sources': sources, 'reason': reason}},
            'realized_observables': {'diagnostic_motion': motion} if status == 'met' else {}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--history', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    value = classify(args.case, args.packet, args.history, args.plan)
    if args.result.exists():
        raise ValueError('physical diagnostic result exists')
    args.result.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    print(value['physical_checks']['maneuver']['status'])


if __name__ == '__main__':
    main()
