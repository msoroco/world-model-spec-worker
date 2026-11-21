"""Test physical-completion classification on source-shaped CPU fixtures.

These diagnostics do not assert that a CARLA maneuver occurred.
"""

import argparse
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ending_road_measurement import measure


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ('capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def opposing_left_fixture(case_id, kind, entry, diagnostic):
    construction = json.loads((HERE / entry['construction']).read_text())
    source = next(item['content'] for item in construction['files']
                  if item['path'] == 'opposing_left_measurement.py')
    names = ('opposing_left_context.json', 'opposing_left_participants.jsonl',
             'video_frames.jsonl')
    with TemporaryDirectory(prefix='c295149-opposing-physical-',
                            dir=ROOT / '.runtime-work') as tmp:
        base = Path(tmp)
        for name in names:
            (base / name).write_text(diagnostic[name])
        module_path = base / 'opposing_left_measurement.py'
        module_path.write_text(source)
        spec = spec_from_file_location('fixture_opposing_left_measurement', module_path)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        context = json.loads((base / names[0]).read_text())
        target = context['turning_route'][-1]['xy']
        participants = base / names[1]
        rows = [json.loads(line) for line in participants.read_text().splitlines()]
        frame_map = [json.loads(line) for line in (base / names[2]).read_text().splitlines()]
        if kind == 'missing_evidence':
            participants.unlink()
        elif kind == 'complete_motion':
            last = rows[-1]
            last_map = frame_map[-1]
            center = [sum(point[axis] for point in last['turning_corners']) / 4
                      for axis in (0, 1)]
            for step in range(1, 5):
                row = json.loads(json.dumps(last))
                row['frame'] = last['frame'] + step
                row['time_s'] = last['time_s'] + .05 * step
                shift = [(target[axis] - center[axis]) * step / 4 for axis in (0, 1)]
                row['turning_corners'] = [[point[axis] + shift[axis] for axis in (0, 1)]
                                          for point in last['turning_corners']]
                rows.append(row)
                mapped = json.loads(json.dumps(last_map))
                mapped.update(video_frame=last_map['video_frame'] + step,
                              carla_frame=row['frame'], native_frame=row['frame'],
                              time_s=row['time_s'])
                frame_map.append(mapped)
            participants.write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                                            for row in rows))
            (base / names[2]).write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                                                for row in frame_map))
        sources = {name: digest(base / name) for name in names if (base / name).is_file()}
        if kind == 'missing_evidence':
            try:
                module.measure_opposing_left(base)
            except ValueError as error:
                if 'Missing required source' not in str(error):
                    raise
            else:
                raise ValueError('Missing opposing-left source was accepted')
            observation, status = None, 'unverified'
        else:
            observation = module.measure_opposing_left(base)['value']
            final = rows[-1]['turning_corners']
            center = [sum(point[axis] for point in final) / 4 for axis in (0, 1)]
            distance = sum((center[axis] - target[axis]) ** 2 for axis in (0, 1)) ** .5
            completed = (distance < .01 and
                         observation['observed_turn_heading_change_rad'] > 1.5)
            status = 'met' if completed else 'not_met'
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Opposing-left fixture did not distinguish completed route exit')
        return {
            'case_id': case_id, 'fixture_kind': kind, 'diagnostic_fixture': True,
            'actual_native_capture': False, 'provenance_kind': 'synthetic_fixture',
            'physical_checks': {'maneuver': {
                'status': status,
                'method': 'original source-shaped turning body center reaches source route exit after heading change',
                'sources': sources,
                'missing_evidence': [names[1]] if kind == 'missing_evidence' else [],
            }},
            'maneuver_completed': status == 'met',
            'realized_observables': ({'turn_heading_change_rad':
                                      observation['observed_turn_heading_change_rad'],
                                      'route_exit_center_distance_m': distance}
                                     if observation else {}),
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
        }


def fixture(case_id, kind):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((case for case in manifest['cases'] if case['case_id'] == case_id), None)
    if entry is None or kind not in KINDS:
        raise ValueError('Unknown exact case or physical fixture kind')
    recipe = json.loads((ROOT / entry['fixture_recipe']).read_text())
    diagnostic = json.loads((ROOT / recipe['generator']['source']).read_text())['files']
    (ROOT / '.runtime-work').mkdir(exist_ok=True)
    if case_id.endswith('__opposing_left_exception'):
        return opposing_left_fixture(case_id, kind, entry, diagnostic)
    names = ('intersection_topology.json', 'intersection_participants.jsonl',
             'trace.jsonl', 'video_frames.jsonl')
    with TemporaryDirectory(prefix='c295149-physical-', dir=ROOT / '.runtime-work') as tmp:
        base = Path(tmp)
        for name in names:
            (base / name).write_text(diagnostic[name])
        participants = base / names[1]
        if kind == 'missing_evidence':
            participants.unlink()
        elif kind == 'incomplete_motion':
            rows = [json.loads(line) for line in participants.read_text().splitlines()]
            for row in rows:
                row['subject_corners'] = [[point[0] + 1000, point[1] + 1000]
                                          for point in row['subject_corners']]
            participants.write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                                            for row in rows))
        sources = {name: digest(base / name) for name in names if (base / name).is_file()}
        observation = None
        if kind == 'complete_motion':
            observation = measure(base / names[0], participants)
            status = ('met' if observation['subject_entry_frame'] is not None and
                      observation['other_entry_frame'] is not None else 'not_met')
        else:
            try:
                measure(base / names[0], participants)
            except ValueError as error:
                reason = str(error).lower()
                if kind == 'missing_evidence' and 'missing required source' not in reason:
                    raise
                if kind == 'incomplete_motion' and 'never enters' not in reason:
                    raise
            else:
                raise ValueError('Incomplete source was accepted as physical completion')
            status = 'unverified' if kind == 'missing_evidence' else 'not_met'
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Physical fixture outcome differs from expected source result')
        return {
            'case_id': case_id, 'fixture_kind': kind, 'diagnostic_fixture': True,
            'actual_native_capture': False, 'provenance_kind': 'synthetic_fixture',
            'physical_checks': {'maneuver': {
                'status': status,
                'method': 'original source-shaped subject and other body-polygon conflict entry',
                'sources': sources,
                'missing_evidence': [names[1]] if kind == 'missing_evidence' else [],
            }},
            'maneuver_completed': status == 'met',
            'realized_observables': ({'subject_entry_frame': observation['subject_entry_frame'],
                                      'other_entry_frame': observation['other_entry_frame']}
                                     if observation else {}),
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
        }


def lifecycle(case_id):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    if case_id not in {entry['case_id'] for entry in manifest['cases']}:
        raise ValueError('Unknown exact case')
    state = {'capture_finished': False, 'encoders_closed': False,
             'restoration_verified': False, 'native_exit': False,
             'owner_released': False}
    observed = []
    for event in EVENTS:
        if event == 'encoders_closed' and not state['capture_finished']:
            raise ValueError('Encoder close precedes capture finish')
        if event == 'native_exit' and not (state['encoders_closed'] and
                                           state['restoration_verified']):
            raise ValueError('Native exit precedes cleanup')
        if event == 'owner_released' and not state['native_exit']:
            raise ValueError('Owner release precedes Native exit')
        if event == 'saved_processing_started' and not state['owner_released']:
            raise ValueError('Saved processing precedes owner release')
        if event in state:
            state[event] = True
        observed.append(event)
    assert tuple(observed) == EVENTS
    return {'case_id': case_id, 'events': observed,
            'scope': 'synthetic ownership-order protocol; no Native process run'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True, choices=KINDS + ('lifecycle',))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = lifecycle(args.case) if args.kind == 'lifecycle' else fixture(args.case, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(args.case, args.kind,
          result.get('physical_checks', {}).get('maneuver', {}).get('status', 'ordered'),
          'synthetic_fixture_only')
