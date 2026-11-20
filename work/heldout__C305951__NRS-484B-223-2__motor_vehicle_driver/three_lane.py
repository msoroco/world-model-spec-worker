"""Three-lane scene requests and original lane occupancy observations."""
from __future__ import annotations

CASES={
 'right_baseline':('right','none'), 'left_travel':('left','none'), 'center_no_exception':('center','none'),
 'center_pass_clear':('center','passing_clear'), 'center_pass_occluded':('center','passing_occluded'),
 'center_prepare_left':('center','left_turn_preparation'),
 'center_allocated_signed':('center','allocated_signed'),
 'center_allocated_unsigned':('center','allocated_unsigned'),
}

def construct(adapter,case_name):
    if case_name not in CASES:raise ValueError('unknown three-lane exact case')
    lane,variant=CASES[case_name]
    road=adapter.road(layout='three_lane_road',clearly_marked_lanes=3)
    marks=[adapter.lane_marking(road=road,boundary=i) for i in (0,1,2,3)]
    features=[]
    if variant.startswith('passing'):
        features.append(adapter.vehicle(role='passed_vehicle',lane='right',target_mps=2))
        if variant=='passing_occluded':
            features.append(adapter.occluder(role='sight_block',position_m=55,height_m=2.5))
    elif variant=='left_turn_preparation':
        features.append(adapter.turn_route(origin_lane='center',direction='left'))
    elif variant.startswith('allocated'):
        features.append(adapter.lane_allocation(lane='center',direction='ego_direction'))
        if variant=='allocated_signed':features.append(adapter.sign(type='center_lane_allocation',direction='ego_direction'))
    ego=adapter.vehicle(role='ego',lane=lane,target_mps=4)
    return {'road':road,'lane_markings':marks,'features':features,'ego':ego}

def measure(context,frames):
    if context.get('marked_lane_count')!=3 or not context.get('marking_source') or not context.get('allocation_source'):
        raise ValueError('original three-lane markings or allocation source missing')
    if context.get('exception_variant') not in ('none','passing_clear','passing_occluded','left_turn_preparation','allocated_signed','allocated_unsigned'):
        raise ValueError('exception premise missing')
    if context.get('exception_variant').startswith('passing') and (not context.get('passing_source') or not context.get('sight_source')):
        raise ValueError('passing and sight source required')
    if context.get('exception_variant').startswith('allocated') and not context.get('sign_source'):
        raise ValueError('posted allocation sign source required')
    if not isinstance(frames,list) or len(frames)<2:raise ValueError('original lane frames missing')
    rows=[]
    for i,r in enumerate(frames):
        if r.get('frame')!=i or r.get('lane') not in ('right','center','left') or not r.get('body_source'):
            raise ValueError('original body lane frame missing')
        rows.append({'frame':i,'lane':r['lane']})
    return {'exception_variant':context['exception_variant'],
            'occupied_lanes':sorted(set(r['lane'] for r in rows)),
            'extreme_left_occupied':any(r['lane']=='left' for r in rows),
            'center_occupied':any(r['lane']=='center' for r in rows),
            'samples':rows,'legal_lane_judgment':None}

def audit_comparison(a,b,variable):
    if variable not in ('lane_occupancy','passing_visibility','turn_preparation','allocation_sign') or not a.get('samples') or not b.get('samples'):
        raise ValueError('original two-case lane comparison required')
    for key in ('road_hash','marking_hash','camera_plan_hash','duration_s','actor_hash'):
        if not a.get(key) or a[key]!=b.get(key):raise ValueError('fixed condition changed: '+key)
    varied='occupied_lanes' if variable=='lane_occupancy' else 'exception_variant'
    fixed='exception_variant' if variable=='lane_occupancy' else 'occupied_lanes'
    if a.get(fixed)!=b.get(fixed):raise ValueError('held condition changed: '+fixed)
    if a.get(varied)==b.get(varied):raise ValueError('deliberate difference absent')
    return {'comparison_complete':True,'variable':variable,'legal_lane_judgment':None}


def prove_physical_preparation(case_id):
    """Exercise current source assessment and capture closure with CPU fixtures."""
    from hashlib import sha256
    import json
    from pathlib import Path
    import sys
    import tempfile

    root = Path(__file__).resolve().parents[2]
    folder = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / 'runtime/scenario_pipeline'))
    from worker_exchange.native_output import assess_physical
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure

    def digest(path):
        return sha256(Path(path).read_bytes()).hexdigest()

    def write(path, value):
        Path(path).write_text(json.dumps(value, indent=2) + '\n')

    manifest_path = folder / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entries = [e for e in manifest['cases'] if not case_id or e['case_id'] == case_id]
    if not entries:
        raise ValueError('Unknown selected case')
    for entry in entries:
        case = entry['case_id']
        name = case.rsplit('__', 1)[-1]
        construction = json.loads((folder / entry['construction']).read_text())
        cfg = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
        frames = round(cfg['duration_s'] * cfg['rate_hz'])
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            with tempfile.TemporaryDirectory(prefix='c305951-physical-', dir=root / '.runtime-work') as tmp:
                attempt = Path(tmp)
                write(attempt / 'config.json', cfg)
                (attempt / 'video_frames.jsonl').write_text(''.join(json.dumps({'video_frame': i, 'carla_frame': 1000+i, 'time_s': round(i/20, 5)}) + '\n' for i in range(frames)))
                if kind != 'missing_evidence':
                    distance = 40 if kind == 'complete_motion' else 2
                    (attempt / 'trace.jsonl').write_text(''.join(json.dumps({'frame': 1000+i, 'time_s': round(i/20, 5), 'position_m': [distance*i/(frames-1), 0, 0]}) + '\n' for i in range(frames)))
                assessed = assess_physical(attempt, cfg)
                expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met', 'missing_evidence': 'unverified'}[kind]
                actual = assessed['physical_checks']['maneuver']['status']
                if actual != expected:
                    raise AssertionError(f'{case} {kind}: {actual}, expected {expected}')
                result = {'format': 'worker-physical-source-protocol-fixture', 'case_id': case,
                          'fixture_kind': kind, 'diagnostic_fixture': True,
                          'provenance_kind': 'synthetic_fixture',
                          'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
                          'physical_checks': assessed['physical_checks'],
                          'maneuver_completed': assessed['maneuver_completed'],
                          'realized_observables': assessed['realized_observables']}
                result_name = 'physical-' + kind + '.json'
                if name != 'right_baseline':
                    result_name = name + '-' + result_name
                write(folder / result_name, result)
                fixtures.append({'kind': kind, 'command': f'.venv-cpu/bin/python work/{folder.name}/three_lane.py --case {case}',
                                 'exit_code': 0, 'log': result_name, 'log_sha256': digest(folder / result_name),
                                 'result': result_name, 'result_sha256': digest(folder / result_name)})
        with tempfile.TemporaryDirectory(prefix='c305951-lifecycle-', dir=root / '.runtime-work') as tmp:
            attempt = Path(tmp)
            (attempt / 'construction.json').write_bytes((folder / entry['construction']).read_bytes())
            (attempt / 'runner.py').write_bytes((folder / 'runner.py').read_bytes())
            seal = {'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
                    'sources': {}, 'native_revision': {'construction_sha256': digest(attempt / 'construction.json'),
                                                        'runner_sha256': digest(attempt / 'runner.py')}}
            write(attempt / 'capture-seal.json', seal)
            try:
                acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
            except ValueError as error:
                if 'has not exited' not in str(error):
                    raise
            else:
                raise AssertionError('Early owner release accepted')
            record_native_exit(attempt)
            acknowledge_owner_release(attempt, attempt / 'owner-release.json', True)
            _closure(attempt, attempt / 'owner-release.json', 'native', False)
        events = seal['events'] + ['native_exit', 'owner_released', 'saved_processing_started']
        lifecycle_log = folder / fixtures[0]['result']
        complete_result = json.loads(lifecycle_log.read_text())
        complete_result['lifecycle_test'] = {
            'events': events,
            'early_owner_release_rejected': True,
            'closure_after_release_accepted': True,
        }
        write(lifecycle_log, complete_result)
        fixtures[0]['result_sha256'] = digest(lifecycle_log)
        fixtures[0]['log_sha256'] = fixtures[0]['result_sha256']
        proof = {'format': 'worker-physical-preparation-proof', 'case_id': case,
                 'construction_sha256': entry['construction_sha256'], 'fixtures': fixtures,
                 'lifecycle': {'events': events, 'exit_code': 0,
                               'log': fixtures[0]['result'], 'log_sha256': fixtures[0]['result_sha256']}}
        receipt_name = name + '-physical-preparation.json'
        write(folder / receipt_name, proof)
        entry['physical_preparation'] = {'receipt': receipt_name, 'sha256': digest(folder / receipt_name)}
    write(manifest_path, manifest)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--case')
    prove_physical_preparation(parser.parse_args().case)
