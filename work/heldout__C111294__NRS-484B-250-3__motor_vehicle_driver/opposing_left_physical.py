"""Synthetic source protocol for the local C111294 opposing-left case."""
import argparse
import hashlib
import json
import shutil
import sys
from math import atan2, cos, hypot, sin
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path.cwd()
PKG = ROOT / 'work/heldout__C111294__NRS-484B-250-3__motor_vehicle_driver'
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from opposing_left_measurement import measure_opposing_left


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, values):
    path.write_text(''.join(json.dumps(value, sort_keys=True) + '\n' for value in values))


def center(corners):
    return [sum(point[axis] for point in corners) / len(corners) for axis in (0, 1)]


def assess(root):
    root = Path(root)
    names = ('opposing_left_context.json', 'opposing_left_participants.jsonl',
             'trace.jsonl', 'video_frames.jsonl')
    sources = {name: sha(root / name) for name in names if (root / name).is_file()}
    if 'opposing_left_participants.jsonl' not in sources:
        try:
            measure_opposing_left(root)
        except ValueError as error:
            if 'Missing required source: opposing_left_participants.jsonl' not in str(error):
                raise
        else:
            raise ValueError('Missing original opposing-left body source was accepted')
        status, observed = 'unverified', {}
    else:
        observed = measure_opposing_left(root)['value']
        participants, trace, mapping = (rows(root / name) for name in
                                        names[1:])
        if len(participants) != len(trace) or len(trace) != len(mapping):
            raise ValueError('Opposing-left physical source lengths differ')
        for body, motion, frame in zip(participants, trace, mapping):
            if ((body['frame'], body['time_s']) !=
                    (motion['frame'], motion['time_s']) or
                    (body['frame'], body['time_s']) !=
                    (frame['carla_frame'], frame['time_s'])):
                raise ValueError('Opposing-left physical source frame join differs')
            if hypot(*(center(body['opposite_corners'])[axis] - motion['position_m'][axis]
                       for axis in (0, 1))) > .5:
                raise ValueError('Opposing-left traveling subject body differs from trace')
            delta = body['opposite_heading_rad'] - motion['heading_deg'] * 3.141592653589793 / 180
            if abs(atan2(sin(delta), cos(delta))) > .25:
                raise ValueError('Opposing-left traveling subject heading differs from trace')
        turn_motion = hypot(*(center(participants[-1]['turning_corners'])[axis] -
                              center(participants[0]['turning_corners'])[axis]
                              for axis in (0, 1)))
        subject_motion = hypot(*(center(participants[-1]['opposite_corners'])[axis] -
                                 center(participants[0]['opposite_corners'])[axis]
                                 for axis in (0, 1)))
        complete = (observed['planned_left_cross'] >= .5 and
                    observed['approach_heading_dot'] <= -.8 and
                    observed['observed_turn_heading_change_rad'] >= 1.0 and
                    abs(observed['observed_opposite_heading_change_rad']) <= .25 and
                    turn_motion >= 4 and subject_motion >= 6)
        status = 'met' if complete else 'not_met'
        observed = {**observed, 'turn_body_displacement_m': turn_motion,
                    'subject_body_displacement_m': subject_motion}
    return {'case_id': 'heldout__C111294__NRS-484B-250-3__motor_vehicle_driver__opposing_left_travel_subject',
            'fixture_only': True, 'diagnostic_fixture': True, 'actual_native_capture': False,
            'physical_checks': {'maneuver': {'status': status,
                'method': 'joined original Native-shaped route, both body headings and traveling subject trace',
                'sources': sources,
                'missing_evidence': ['opposing_left_participants.jsonl'] if status == 'unverified' else []}},
            'maneuver_completed': status == 'met',
            'realized_observables': observed if status == 'met' else {},
            'provenance_kind': 'synthetic_fixture',
            'provenance_note': 'Native-shaped synthetic source protocol test only',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def run(kind):
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown opposing-left physical fixture kind')
    with TemporaryDirectory(prefix='c111294-opposing-physical-', dir=ROOT / '.runtime-work') as temp:
        folder = Path(temp)
        from worker_exchange.fixture_recipe import materialize
        materialize(ROOT, PKG / 'diagnostic-recipe-opposing-left.json', folder / 'source')
        source = folder / 'source'
        folder = folder / 'working'
        folder.mkdir()
        for name in ('opposing_left_context.json', 'opposing_left_participants.jsonl',
                     'trace.jsonl', 'video_frames.jsonl'):
            shutil.copy2(source / name, folder / name)
        participants = rows(folder / 'opposing_left_participants.jsonl')
        trace = rows(folder / 'trace.jsonl')
        first = participants[0]
        for index, (body, motion) in enumerate(zip(participants, trace)):
            dx = index * 1.0
            body['opposite_corners'] = [[point[0] + dx, point[1]]
                                        for point in body['opposite_corners']]
            motion['position_m'][0] += dx
            if kind == 'incomplete_motion' and index:
                body['turning_corners'] = first['turning_corners']
                body['turning_heading_rad'] = first['turning_heading_rad']
        write_rows(folder / 'opposing_left_participants.jsonl', participants)
        write_rows(folder / 'trace.jsonl', trace)
        if kind == 'missing_evidence':
            (folder / 'opposing_left_participants.jsonl').unlink()
        result = assess(folder)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if result['physical_checks']['maneuver']['status'] != expected:
            raise ValueError('Opposing-left synthetic physical outcome differs')
        result['fixture_kind'] = kind
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(args.kind, result['physical_checks']['maneuver']['status'], 'synthetic_fixture_only')
