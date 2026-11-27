"""Exercise exact red-curb physical completion and lifecycle branches."""

import argparse
import json
from pathlib import Path

from physical_completion import EVENTS, evaluate, lifecycle


def fixture(case_id, kind):
    rows = []
    for i in range(120):
        row = {'case_id': case_id, 'frame': i + 1, 'speed_mps': 0 if kind == 'complete_motion' else 2,
               'inside_red_curb': True, 'trace_source_sha256': 'synthetic-trace',
               'curb_source_sha256': 'synthetic-curb',
               'camera_frame_map_sha256': 'synthetic-frame-map'}
        rows.append(row)
    if kind == 'missing_evidence':
        rows[-1].pop('curb_source_sha256')
    result = evaluate(rows, case_id)
    result.update(case_id=case_id, provenance_kind='synthetic_fixture',
                  diagnostic_fixture=True, fixture_kind=kind)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if result['physical_checks']['maneuver']['status'] != expected:
        raise ValueError('physical fixture branch mismatch')
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--fixture', required=True, choices=('complete_motion', 'incomplete_motion',
                                                       'missing_evidence', 'lifecycle'))
    p.add_argument('--output', required=True)
    args = p.parse_args()
    result = fixture(args.case, args.fixture) if args.fixture != 'lifecycle' else lifecycle(EVENTS)
    if args.fixture == 'lifecycle':
        try:
            lifecycle(('saved_processing_started',) + EVENTS[:-1])
        except ValueError:
            result['rejected_early_saved_processing'] = True
        else:
            raise ValueError('lifecycle accepted early processing')
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': args.case, 'fixture': args.fixture, 'passed': True}))


if __name__ == '__main__':
    main()
