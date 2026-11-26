"""CPU fixture checker for standing completion and owner lifecycle ordering."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def check_motion(spec, base):
    if spec.get('diagnostic_fixture') is not True:
        raise ValueError('physical checker accepts diagnostic fixtures only')
    source = spec.get('ticks')
    if source is None:
        status, sources, count = 'unverified', {'fixture': spec['fixture_id']}, 0
    else:
        path = (Path(base) / source).resolve()
        if (not path.is_file() or not path.is_relative_to(Path(base).resolve()) or
                hashlib.sha256(path.read_bytes()).hexdigest() != spec.get('ticks_sha256')):
            raise ValueError('physical fixture source bytes changed')
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if len(rows) != 9 or any(row.get('original_frame') is None or
                                 row.get('ego_speed_mps') is None for row in rows):
            raise ValueError('physical fixture frame source malformed')
        count = sum(row['ego_speed_mps'] <= .01 for row in rows)
        status = 'met' if count >= 2 else 'not_met'
        sources = {source: spec['ticks_sha256']}
    return {'physical_checks': {'maneuver': {
                'status': status, 'method': 'original-frame standing count',
                'sources': sources}},
            'maneuver_completed': status == 'met',
            'realized_observables': ({'standing_frame_count': count}
                                     if status == 'met' else {}),
            'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True, 'legal_verdict_claimed': False}


def check_lifecycle(spec):
    if spec.get('events') != EVENTS:
        raise ValueError('saved processing precedes owner release')
    return {'events': EVENTS, 'saved_started_after_owner_release': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--lifecycle', action='store_true')
    args = parser.parse_args()
    spec = json.loads(args.fixture.read_text())
    result = check_lifecycle(spec) if args.lifecycle else check_motion(spec, args.fixture.parent)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('diagnostic fixture checked')


if __name__ == '__main__':
    main()
