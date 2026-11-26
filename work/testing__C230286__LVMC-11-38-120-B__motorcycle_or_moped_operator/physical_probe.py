"""Diagnostic CPU proof of requested motion and source absence classification."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(source, requested_motion, mode):
    path = Path(source)
    if mode == 'missing_evidence':
        rows = []
        sources = {'lamp_trace': 'missing'}
    else:
        rows = [json.loads(line) for line in path.read_text().splitlines() if line]
        sources = {'lamp_trace': sha(path)}
        if mode == 'incomplete_motion':
            rows = [dict(row, speed_mps=(0 if requested_motion else 5)) for row in rows]
    valid = len(rows) >= 9 and all(row.get('carla_frame') == rows[0]['carla_frame'] + i
        and row.get('frame') == i and isinstance(row.get('speed_mps'), (int, float))
        for i, row in enumerate(rows))
    matches = valid and all((row['speed_mps'] > 0.05) == requested_motion for row in rows)
    status = 'unverified' if not rows or not valid else ('met' if matches else 'not_met')
    return {
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'maneuver_completed': status == 'met',
        'realized_observables': {'sampled_frames': len(rows), 'requested_motion': requested_motion,
            'speed_mps': [row['speed_mps'] for row in rows]} if status == 'met' else {},
        'physical_checks': {'maneuver': {
            'status': status,
            'method': 'original 20 Hz vehicle speed readback compared with requested motion; diagnostic fixture only',
            'sources': sources,
            'intervals': [[rows[0]['time_s'], rows[-1]['time_s']]] if rows else [],
            'legal_verdict_claimed': False}},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--requested-motion', choices=('moving', 'stopped'), required=True)
    parser.add_argument('--mode', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = assess(args.source, args.requested_motion == 'moving', args.mode)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met', 'missing_evidence': 'unverified'}[args.mode]
    if result['physical_checks']['maneuver']['status'] != expected:
        raise ValueError('Diagnostic physical outcome differed from expected source state')
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'mode': args.mode, 'status': expected, 'source': result['physical_checks']['maneuver']['sources']}, sort_keys=True))


if __name__ == '__main__':
    main()
