"""Synthetic source-shaped checks of physical outcome and capture closure.

The fixtures exercise the saved assessment code. They are diagnostic inputs,
never observations from an actual CARLA run or legal endangerment findings.
"""

import argparse
import hashlib
import json
from pathlib import Path

from endangerment_finalizer import analyze, build_result


HERE = Path(__file__).resolve().parent


def square(x):
    return [[x - .5, -.5], [x + .5, -.5], [x + .5, .5], [x - .5, .5]]


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def rows(path, values):
    path.write_text(''.join(json.dumps(value) + '\n' for value in values))


def fixture(case_id, kind, output):
    suffix = case_id.split('__')[-1]
    construction = json.loads((HERE / f'cases/construction-{suffix}.json').read_text())
    if construction['case_id'] != case_id:
        raise ValueError('Exact construction differs from requested case')
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    if config['duration_s'] != 8 or config['rate_hz'] != 20:
        raise ValueError('Fixture must use the exact 160-frame capture contract')
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'config.json', config)
    # Native-shaped provenance is for exercising the pinned physical-result
    # validator. The explicit diagnostic flag prevents delivery interpretation.
    write(output / 'acquisition-provenance.json',
          {'provenance_kind': 'native', 'diagnostic_fixture': True,
           'fixture_scope': 'CPU simulation of original-source protocol'})
    count = 160
    total = config['requested_speed_mps'] * 8.0 if kind == 'complete_motion' else 1.0
    exposed_x = 10.0
    frames, trace, footprints = [], [], []
    for index in range(count):
        time_s = index / 20
        x = total * index / (count - 1)
        frames.append({'video_frame': index, 'carla_frame': index, 'time_s': time_s})
        trace.append({'frame': index, 'time_s': time_s, 'position_m': [x, 0]})
        footprints.append({'frame': index, 'time_s': time_s,
                           'ego_id': 'fixture-ego', 'exposed_id': 'fixture-exposed',
                           'exposed_kind': config['exposed_kind'],
                           'ego_corners_xy': square(x),
                           'exposed_corners_xy': square(exposed_x),
                           'ego_velocity_xy_mps': [total / 8, 0],
                           'exposed_velocity_xy_mps': [0, 0]})
    rows(output / 'video_frames.jsonl', frames)
    rows(output / 'trace.jsonl', trace)
    rows(output / 'exposed_actor_footprints.jsonl', footprints)
    if kind == 'missing_evidence':
        (output / 'trace.jsonl').unlink()
        from worker_exchange.native_output import physical_result
        result = physical_result(output, {'case_id': case_id, 'target_checks': []})
    else:
        report = analyze(output)
        result = build_result(output, report)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if result['physical_checks']['maneuver']['status'] != expected:
        raise ValueError('Physical outcome differs from fixture control')
    if result['maneuver_completed'] != (expected == 'met'):
        raise ValueError('Completion boolean differs from original-body outcome')
    if kind == 'complete_motion' and not result['physical_checks']['maneuver']['details']['passage_observed']:
        raise ValueError('Complete fixture lacks before/after body passage')
    if kind == 'incomplete_motion' and result['physical_checks']['maneuver']['details']['passage_observed']:
        raise ValueError('Incomplete fixture unexpectedly passed exposed body')
    if result['physical_acceptance_claimed'] is not False or result['diagnostic_fixture'] is not True:
        raise ValueError('Synthetic physical fixture claimed delivery acceptance')
    result['fixture_scope'] = 'synthetic CPU original-source protocol; no actual Native observation'
    write(HERE / 'physical' / f'{suffix}-{kind}-result.json', result)
    print(json.dumps({'case_id': case_id, 'kind': kind, 'status': expected,
                      'source_sha256': {
                          name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                          for name in ('config.json', 'video_frames.jsonl', 'exposed_actor_footprints.jsonl')},
                      'physical_acceptance_claimed': False}, indent=2))


def lifecycle(case_id, output):
    from worker_exchange.native_output import seal_capture
    suffix = case_id.split('__')[-1]
    construction = HERE / f'cases/construction-{suffix}.json'
    output.mkdir(parents=True, exist_ok=False)
    (output / 'construction.json').write_bytes(construction.read_bytes())
    (output / 'runner.py').write_text(next(
        item['content'] for item in json.loads(construction.read_text())['files']
        if item['path'] == 'runner.py'))
    (output / 'trace.jsonl').write_text('{"frame":0,"time_s":0}\n')
    (output / 'video_frames.jsonl').write_text('{"video_frame":0,"carla_frame":0,"time_s":0}\n')
    rejected = False
    try:
        seal_capture(output, frames=1, restoration={'restored': False}, errors=[],
                     encoder_exit_codes={'overview': 0})
    except ValueError as error:
        rejected = 'verified restoration' in str(error)
    if not rejected or (output / 'capture-seal.json').exists():
        raise ValueError('Premature seal was not rejected')
    seal = seal_capture(output, frames=1, restoration={'restored': True}, errors=[],
                        encoder_exit_codes={'overview': 0})
    if seal['events'] != ['capture_finished', 'encoders_closed', 'restoration_verified']:
        raise ValueError('Capture closure event order differs')
    events = seal['events'] + ['native_exit', 'owner_released', 'saved_processing_started']
    print(json.dumps({'case_id': case_id, 'events': events,
                      'premature_seal_rejected': rejected,
                      'seal_sha256': hashlib.sha256((output / 'capture-seal.json').read_bytes()).hexdigest(),
                      'physical_acceptance_claimed': False}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.kind == 'lifecycle':
        lifecycle(args.case, Path(args.output))
    else:
        fixture(args.case, args.kind, Path(args.output))


if __name__ == '__main__':
    main()
