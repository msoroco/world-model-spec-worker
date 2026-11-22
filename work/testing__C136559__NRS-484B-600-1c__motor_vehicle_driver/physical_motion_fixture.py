"""Synthetic source-bound travel and capture lifecycle probes for posted-speed cases."""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.common import sha  # noqa: E402
from worker_exchange.native_output import physical_result, seal_capture  # noqa: E402
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release  # noqa: E402


def read(path):
    return json.loads(Path(path).read_text())


def derive_speed_source(source, output, target_mph):
    """Make an openly synthetic, kinematically joined diagnostic from a seed.

    This does not change the original recording or represent Native observation.
    The four source cameras remain synthetic black frames from the seed.
    """
    if not 0 < target_mph < 80:
        raise ValueError('Diagnostic target out of range')
    original = Path(source).read_bytes()
    data = json.loads(original)
    files = data['files']
    streams = {name: [json.loads(line) for line in files[name].splitlines() if line]
               for name in ('subject_motion.jsonl', 'trace.jsonl',
                            'speed_samples.jsonl', 'body_history.jsonl',
                            'capture/evidence.jsonl')}
    count = len(streams['trace.jsonl'])
    if count != 9 or any(len(rows) != count for rows in streams.values()):
        raise ValueError('Seed frame streams are not the expected nine-frame join')
    speed = target_mph * 0.44704
    first = streams['trace.jsonl'][0]
    t0 = first['time_s']
    x0 = first['position_m'][0]
    subject = streams['subject_motion.jsonl'][0]['subject_actor_id']

    def body_shift(points, dx):
        return [[point[0] + dx, *point[1:]] for point in points]

    def participant_shift(row, dx, x):
        if row.get('actor_id') != subject:
            return
        row['position_m'][0] = x
        row['velocity_mps'] = [speed, 0.0, 0.0]
        row['speed_mps'] = speed
        row['body_vertices_m'] = body_shift(row['body_vertices_m'], dx)

    for index in range(count):
        motion = streams['subject_motion.jsonl'][index]
        trace = streams['trace.jsonl'][index]
        sample = streams['speed_samples.jsonl'][index]
        history = streams['body_history.jsonl'][index]
        evidence = streams['capture/evidence.jsonl'][index]
        if not (motion['frame'] == trace['frame'] == sample['frame'] == history['frame']
                == evidence['original_frame']):
            raise ValueError('Seed frame join changed')
        x = x0 + speed * (trace['time_s'] - t0)
        dx = x - trace['position_m'][0]
        motion['velocity_mps'] = [speed, 0.0, 0.0]
        motion['speed_mps'] = speed
        motion['speed_source'] = 'synthetic_kinematic_derivation'
        motion['road_s_m'] = x
        for row in (trace, sample):
            row['position_m'][0] = x
            row['position']['x'] = x
            row['velocity_mps'] = [speed, 0.0, 0.0]
            row['speed_mps'] = speed
            row['speed_mph'] = target_mph
            row['accel_longitudinal_mps2'] = 0.0
            row['control'] = {'throttle': 0.0, 'steer': 0.0, 'brake': 0.0,
                              'hand_brake': False, 'reverse': False,
                              'manual_gear_shift': False, 'gear': 0}
        history['vertices_m'] = body_shift(history['vertices_m'], dx)
        ego = evidence['ego']
        ego['position_m'][0] = x
        ego['speed_mps'] = speed
        # The frozen adapter accepts this label only in diagnostic-fixture mode.
        # fixture-provenance.json retains the more specific kinematic derivation.
        ego['speed_provenance'] = 'synthetic_native_sample'
        ego['body_vertices_m'] = body_shift(ego['body_vertices_m'], dx)
        evidence['world']['road_projection']['s_m'] = x
        for participant in evidence['original_observations']['participants']:
            participant_shift(participant, dx, x)
        for sensor in evidence['original_observations']['rgb_sensors']:
            if sensor.get('parent_actor_id') == subject:
                sensor['position_m'][0] += dx
        evidence['supporting_only']['applied_control'] = trace['control']
        for graph in data['graphs']:
            if graph['attributes'].get('frame') != trace['frame']:
                continue
            observed = graph['attributes'].get('observed_evidence', {})
            for participant in observed.get('participants', []):
                participant_shift(participant, dx, x)
            for sensor in observed.get('rgb_sensors', []):
                if sensor.get('parent_actor_id') == subject:
                    sensor['position_m'][0] += dx

    for name, rows in streams.items():
        files[name] = ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)
    provenance = json.loads(files['fixture-provenance.json'])
    provenance.update({'scope': 'Derived CPU diagnostic motion and synthetic black cameras; never Native or physical evidence.',
                       'derivation': 'constant-speed x(t), 20 Hz',
                       'seed_sha256': hashlib.sha256(original).hexdigest(),
                       'synthetic_target_mph': target_mph})
    files['fixture-provenance.json'] = json.dumps(provenance, separators=(',', ':')) + '\n'
    manifest = json.loads(files['capture/manifest.json'])
    manifest['acquisition'] = 'synthetic_diagnostic_derivation'
    manifest['source_run'] = 'synthetic:constant-speed-derived-from-retained-seed'
    manifest['speed_source'] = 'synthetic_kinematic_derivation'
    for name in manifest['sources']:
        if name in files:
            manifest['sources'][name] = hashlib.sha256(files[name].encode()).hexdigest()
    files['capture/manifest.json'] = json.dumps(manifest, separators=(',', ':')) + '\n'
    verify_derived_source(data, target_mph)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, separators=(',', ':'), allow_nan=False) + '\n')
    result = {'output': str(output), 'sha256': sha(output), 'seed_sha256': provenance['seed_sha256'],
              'target_mph': target_mph, 'frames': count, 'scope': 'synthetic_diagnostic_only'}
    return result


def verify_derived_source(data, target_mph):
    """Check that all authored diagnostic motion streams agree frame by frame."""
    files = data['files']
    names = ('subject_motion.jsonl', 'trace.jsonl', 'speed_samples.jsonl',
             'body_history.jsonl', 'capture/evidence.jsonl')
    streams = [[json.loads(line) for line in files[name].splitlines() if line]
               for name in names]
    speed = target_mph * 0.44704
    initial_time = streams[1][0]['time_s']
    initial_x = streams[1][0]['position_m'][0]
    for index, (motion, trace, sample, body, evidence) in enumerate(zip(*streams)):
        frame = motion['frame']
        if any(row['frame'] != frame for row in (trace, sample, body)) or evidence['original_frame'] != frame:
            raise AssertionError('Derived frame join differs')
        x = initial_x + speed * (trace['time_s'] - initial_time)
        if any(abs(value - x) > 1e-7 for value in (
                motion['road_s_m'], trace['position_m'][0], trace['position']['x'],
                sample['position_m'][0], evidence['ego']['position_m'][0],
                evidence['world']['road_projection']['s_m'])):
            raise AssertionError('Derived position disagrees')
        if any(abs(value - speed) > 1e-7 for value in (
                motion['velocity_mps'][0], motion['speed_mps'], trace['speed_mps'],
                sample['speed_mps'], evidence['ego']['speed_mps'])):
            raise AssertionError('Derived velocity disagrees')
        if abs(trace['speed_mph'] - target_mph) > 1e-7:
            raise AssertionError('Derived mph disagrees')
        if any(abs(vertices[0][0] - body['vertices_m'][0][0]) > 1e-7
               for vertices in (evidence['ego']['body_vertices_m'],
                                evidence['original_observations']['participants'][0]['body_vertices_m'])):
            raise AssertionError('Derived body geometry disagrees')
        graph = next(g for g in data['graphs'] if g['attributes'].get('frame') == frame
                     and g['nodes'])
        participant = graph['attributes']['observed_evidence']['participants'][0]
        if abs(participant['position_m'][0] - x) > 1e-7:
            raise AssertionError('Derived graph observation disagrees')
    if len(streams[0]) != 9 or any(len(rows) != 9 for rows in streams):
        raise AssertionError('Derived diagnostic lost a frame')
    return {'frames': 9, 'target_mph': target_mph, 'source_consistency_passed': True,
            'physical_acceptance_claimed': False}


def verify_derived_boundary(paths):
    """Compare only explicitly synthetic sources; never assert Native delivery."""
    targets = (24.9, 25.0, 25.1)
    if len(paths) != len(targets):
        raise ValueError('Boundary needs below, at and above diagnostic sources')
    sources = [read(path) for path in paths]
    contexts = [json.loads(item['files']['sign_context.json']) for item in sources]
    fixed = ('native_map_id', 'governed_road_id', 'zone_start_s_m',
             'zone_end_s_m', 'posted_limit_value', 'posted_unit')
    if any(tuple(context[key] for key in fixed) != tuple(contexts[0][key] for key in fixed)
           for context in contexts[1:]):
        raise AssertionError('Diagnostic fixed conditions differ')
    checks = [verify_derived_source(item, target) for item, target in zip(sources, targets)]
    if contexts[0]['posted_limit_value'] != 25 or contexts[0]['posted_unit'] != 'mph':
        raise AssertionError('Diagnostic posting differs')
    return {'kind': 'synthetic_diagnostic_boundary', 'source_checks': checks,
            'observed_speed_order': list(targets), 'difference_observed': True,
            'physical_acceptance_claimed': False, 'delivery_ready': False}


def run(case, kind, output=None):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((item for item in manifest['cases'] if item['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown exact selected case')
    construction_path = HERE / entry['construction']
    if sha(construction_path) != entry['construction_sha256']:
        raise ValueError('Exact construction changed')
    construction = read(construction_path)
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    recipe = read(REPO / entry['fixture_recipe'])
    source = REPO / recipe['generator']['source']
    if sha(source) != recipe['generator']['sha256']:
        raise ValueError('Synthetic diagnostic source changed')
    files = read(source)['files']
    with tempfile.TemporaryDirectory(prefix='c136559-physical-', dir=REPO / '.runtime-work') as temp:
        attempt = Path(temp)
        (attempt / 'config.json').write_text(json.dumps(config) + '\n')
        for name in ('trace.jsonl', 'video_frames.jsonl'):
            (attempt / name).write_text(files[name])
        (attempt / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
        if kind == 'lifecycle':
            saved = HERE / entry['saved_processing']['receipt']
            if sha(saved) != entry['saved_processing']['sha256']:
                raise ValueError('Saved-processing receipt changed')
            receipt = read(saved)
            if (receipt.get('case_id') != case or receipt.get('passed') is not True
                    or receipt.get('recorded_only') is not True):
                raise ValueError('No exact recorded-only saved proof')
            (attempt / 'construction.json').write_text(json.dumps(construction) + '\n')
            (attempt / 'runner.py').write_text(next(item['content'] for item in construction['files']
                                                   if item['path'] == 'runner.py'))
            try:
                seal_capture(attempt, frames=9, restoration={'restored': True}, errors=[],
                             encoder_exit_codes={'synthetic_encoder': 1},
                             context={'diagnostic_fixture': True})
            except ValueError as error:
                if 'unclosed/failed encoders' not in str(error):
                    raise
            else:
                raise AssertionError('Failed encoder was sealed')
            sealed = seal_capture(attempt, frames=9, restoration={'restored': True}, errors=[],
                                  encoder_exit_codes={'synthetic_encoder': 0},
                                  context={'diagnostic_fixture': True})
            try:
                acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
            except ValueError as error:
                if 'Native process has not exited' not in str(error):
                    raise
            else:
                raise AssertionError('Owner release preceded Native exit')
            native = record_native_exit(attempt)
            owner = acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
            events = sealed['events'] + [native['event'], owner['event'], 'saved_processing_started']
            expected = ['capture_finished', 'encoders_closed', 'restoration_verified',
                        'native_exit', 'owner_released', 'saved_processing_started']
            if events != expected:
                raise AssertionError('Closure sequence changed')
            result = {'case_id': case, 'events': events, 'diagnostic_fixture': True,
                      'failed_encoder_rejected': True, 'premature_release_rejected': True,
                      'saved_processing_receipt_sha256': sha(saved)}
        else:
            motion = attempt / 'trace.jsonl'
            if kind == 'missing_evidence':
                motion.unlink()
            elif kind == 'complete_motion':
                rows = [json.loads(line) for line in motion.read_text().splitlines()]
                for index, row in enumerate(rows):
                    row['position_m'][0] = 100 + 10 * index
                    row['position']['x'] = 100 + 10 * index
                motion.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            result = physical_result(attempt, {'target_checks': []})
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            check = result['physical_checks']['maneuver']
            if (check['status'] != expected or result['maneuver_completed'] != (expected == 'met')
                    or not check['method'] or not check['sources']
                    or result['provenance_kind'] != 'synthetic_fixture'
                    or result['diagnostic_fixture'] is not True
                    or result['physical_acceptance_claimed'] is not False):
                raise AssertionError('Physical classifier changed')
            if expected == 'met' and not result['realized_observables']:
                raise AssertionError('Complete synthetic travel lacks measured values')
    if output:
        Path(output).write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return {'case_id': case, 'kind': kind, 'diagnostic_fixture': True,
            'physical_acceptance_claimed': False,
            'status': result.get('physical_checks', {}).get('maneuver', {}).get('status', 'lifecycle_passed')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case')
    parser.add_argument('--kind', required=True,
                        choices=('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle', 'derive_speed'))
    parser.add_argument('--output')
    parser.add_argument('--source')
    parser.add_argument('--target-mph', type=float)
    args = parser.parse_args()
    if args.kind == 'derive_speed':
        if not args.source or not args.output or args.target_mph is None:
            parser.error('derive_speed requires --source, --output and --target-mph')
        print(json.dumps(derive_speed_source(args.source, args.output, args.target_mph), sort_keys=True))
    else:
        if not args.case:
            parser.error('case is required for physical probes')
        print(json.dumps(run(args.case, args.kind, args.output), sort_keys=True))
