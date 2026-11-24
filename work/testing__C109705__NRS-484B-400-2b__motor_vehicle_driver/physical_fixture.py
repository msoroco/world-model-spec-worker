"""Exercise source-bound physical outcomes with synthetic 45 s histories.

The generated sources are CPU fixtures. They do not assert that CARLA realized
the route or that the roadway has a particular legal status.
"""
import argparse
import json
import pathlib
import sys


def body(x, y):
    return [[x - .7, y - .7, 0], [x + .7, y - .7, 0],
            [x + .7, y + .7, 0], [x - .7, y + .7, 0]]


def make_sources(root, kind, case_id):
    root = pathlib.Path(root)
    root.mkdir(parents=True, exist_ok=False)
    geometry = {'intersection_xy_m': [[-5, -5], [5, -5], [5, 5], [-5, 5]],
                'approach_road_id': 'A', 'connector_road_id': 'C',
                'departure_road_id': 'B', 'two_way': True,
                'departure_direction_xy': [0, 1]}
    if kind != 'missing_evidence':
        (root / 'road_geometry.json').write_text(json.dumps(geometry, sort_keys=True) + '\n')
    (root / 'config.json').write_text(json.dumps({'selected_case_id': case_id,
                                                  'diagnostic_fixture': True}, sort_keys=True) + '\n')
    with (root / 'body_history.jsonl').open('w') as history, (root / 'video_frames.jsonl').open('w') as frames:
        for i in range(900):
            if i < 300:
                road, x, y = 'A', -60 + 50 * i / 299, -1
            elif i < 600:
                road, x, y = 'C', -4 + 8 * (i - 300) / 299, -4 + 8 * (i - 300) / 299
            else:
                road = 'B'
                x = 0
                y = 1 if kind == 'incomplete_motion' else 10 + 50 * (i - 600) / 299
            row = {'frame': i + 100, 'time_s': i / 20, 'road_id': road,
                   'body_vertices_m': body(x, y)}
            frame = {'video_frame': i, 'carla_frame': i + 100, 'time_s': i / 20}
            history.write(json.dumps(row, sort_keys=True) + '\n')
            frames.write(json.dumps(frame, sort_keys=True) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'), required=True)
    parser.add_argument('--scratch', required=True)
    parser.add_argument('--result', required=True)
    args = parser.parse_args()
    scratch = pathlib.Path(args.scratch).resolve()
    if '.runtime-work' not in scratch.parts:
        raise ValueError('physical fixture scratch must be under .runtime-work')
    if scratch.exists():
        raise ValueError('physical fixture scratch already exists')
    make_sources(scratch, args.kind, args.case)
    from scenario_pipeline.worker_exchange.native_output import assess_left_turn
    assessment = assess_left_turn(scratch)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[args.kind]
    if assessment['status'] != expected:
        raise ValueError('physical fixture yielded ' + assessment['status'] + ', expected ' + expected)
    result = {'case_id': args.case, 'physical_checks': {'maneuver': assessment},
              'maneuver_completed': assessment['status'] == 'met',
              'realized_observables': assessment['observed'],
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
    pathlib.Path(args.result).write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'case_id': args.case, 'fixture': args.kind,
                      'status': assessment['status'], 'sources': sorted(assessment['sources']),
                      'frames': 900}, sort_keys=True))


if __name__ == '__main__':
    main()
