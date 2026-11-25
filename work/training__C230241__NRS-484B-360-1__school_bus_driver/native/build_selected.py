"""Build exact selected school-bus speed probes and route-recovery candidates."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
AID = FOLDER.name
LAW = 'NRS-484B-360-1'
CASES = [AID + '__probe_a', AID + '__probe_b']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    batch = json.loads((REPO / 'batch.json').read_text())
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    assignment = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
    terms = [x['term'] for x in assignment['source_observation_terms']]
    desc = {'channels': [{'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                         'time_window': '30 s / 600 original frames',
                         'method': 'Original post-tick bus velocity, independently reviewed pupil/trip source and four camera frame join',
                         'reference_frame': 'original Native frame',
                         'uncertainty': 'School-bus identity, pupils aboard and school-trip purpose require original source review'}
                        for name in terms + ['bus_speed_mph', 'camera_frame_join']],
            'context_inputs': [{'name': 'pupil_trip_context', 'unit': 'structured',
                                'method': 'Independent review of bus class, original pupil imagery and trip-purpose source'}],
            'limitations': ['Requested controller speed is not observed Native speed.',
                            'Synthetic pupil fixtures do not establish transport or legal outcome.']}
    case_proposals = []
    rows = []
    for suffix, speed in [('probe_a', 52), ('probe_b', 58)]:
        case_id = AID + '__' + suffix
        case_proposals.append({'case_id': case_id, 'target_law_id': LAW,
            'target_type': 'judgment_sweep',
            'rationale': 'Compare source-measured bus speed across the statutory 55 mph cap while requiring original school transportation context.',
            'variable_assignments': {
                'requested_speed_mph': {'kind': 'controller', 'unit': 'mph', 'value': speed},
                'school_trip_and_ice_cream_control': {'kind': 'world_setup', 'unit': 'categorical',
                  'value': 'same reviewed school transportation trip and separate ice cream truck'}},
            'paired_probe_id': AID + '__speed_pair',
            'deliberate_differences': ['requested_speed_mph'],
            'probe': {'primary_variable': 'requested_speed_mph',
                      'comparison_or_standard': 'source-joined original velocity against statutory 55 mph cap',
                      'target_value_or_branch': speed},
            'unresolved_judgment_calls': ['school bus class', 'transporting pupils to or from school',
                                           'original pupil occupancy'],
            'recording_description': desc})
        entry = {'case_id': case_id, 'kind': 'delivery', 'id': 'primary',
                 'candidate_risk': {'status': 'physical',
                    'reason': 'Exact school-bus and ice-cream-truck actor spawns or route geometry can fail.'},
                 'candidates': [], 'measurement_contract': f'measurement-{suffix}.json',
                 'measurement_procedure': {'entrypoint': 'finalize.py',
                                           'output_schema': 'school-bus-saved-speed-analysis-v1'},
                 'fixture_recipe': f'work/{AID}/diagnostic-{suffix}-primary-recipe.json',
                 'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                    'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                 'acquisition': {x['name']: {'entrypoint': 'finalize.py',
                    'method': 'original bus velocity and independent school-trip/pupil source review',
                    'evidence': 'Synthetic diagnostic only; original review pending'}
                    for x in desc['channels']}}
        draft = json.loads((FOLDER / 'draft-primary' / suffix / 'primary/construction.json').read_text())
        for candidate, shift in [('primary', 0), ('fallback1', 1)]:
            cfg = json.loads(next(x['content'] for x in draft['files'] if x['path'] == 'config.json'))
            cfg['selected_case_id'] = case_id
            for camera, view in zip(cfg['cameras'], ('overview', 'approach', 'reference_corner', 'driver_reference')):
                camera['name'] = view
                camera['width'] = 1920 if view == 'overview' else 1280
                camera['height'] = 1080 if view == 'overview' else 720
            cfg['candidate_id'] = candidate
            cfg['spawn_point_index'] = shift
            cfg['recording_description'] = desc
            cfg['physical_completion'] = {'criterion': 'travel_progress', 'motion_source': 'trace.jsonl',
                'position_key': 'position_m', 'minimum_progress_m': 10,
                'engineering_tolerances_not_legal': True}
            files = []
            for f in draft['files']:
                if f['path'] == 'config.json':
                    files.append({'path': 'config.json', 'content': json.dumps(cfg, indent=2) + '\n'})
                else:
                    files.append({'path': f['path'], 'source': f'work/{AID}/native/selected_runner.py', 'content': (FOLDER / 'native/selected_runner.py').read_text()} if f['path'] == 'runner.py' else {'path': f['path'], 'content': f['content']})
            for name in ['measure_speed.py', 'finalize.py']:
                src = FOLDER / ('native/' + name)
                files.append({'path': name, 'source': f'work/{AID}/native/{name}', 'content': src.read_text()})
            construction = {k: v for k, v in draft.items() if k not in ('files', 'status')}
            construction.update(files=files, status='selected_cpu_construction',
                                recording_description=desc,
                                measurement_plan='Measure all original bus velocity frames; independently review bus class, pupils aboard and school trip purpose. No legal verdict from request or fixture.')
            path = FOLDER / 'native/selected-drafts' / suffix / candidate / 'construction.json'
            write(path, construction)
            binding = {'construction': str(path.relative_to(FOLDER)), 'construction_sha256': sha(path)}
            if candidate == 'primary':
                entry.update(binding)
            else:
                entry['candidates'].append({'id': candidate, **binding,
                    'trigger': {'source': 'native-capture-report.json', 'metric': 'actor_spawn_and_route_progress',
                                'failure_condition': 'school bus or truck spawn fails or route progress absent'},
                    'changed_knobs': ['spawn_point_index 0 to 1']})
        rows.append(entry)
        write(FOLDER / f'measurement-{suffix}.json',
              {'format': 'worker-measurement-contract', 'requirements': [
                 {'disposition_index': 0, 'requirement': plan['requirement_dispositions'][0]['requirement'],
                  'source': plan['requirement_dispositions'][0]['source'],
                  'output_key': 'school_bus_speed', 'method': 'measure_school_bus_speed',
                  'value_type': 'object', 'kind': 'measured',
                  'inputs': ['bus_motion.jsonl', 'video_frames.jsonl', 'passenger_trip_review.json']}],
               'negative': {'remove': ['bus_motion.jsonl'],
                            'error_contains': 'Missing required source: bus_motion.jsonl'}})
    write(FOLDER / 'proposals/cases.json',
          {'format': 'worker-case-proposals', 'cell_id': 'C230241', 'actor': 'school_bus_driver',
           'law_id': LAW, 'status': 'draft', 'cases': case_proposals,
           'sweep_specs': [], 'sweeps_expanded': True})
    write(FOLDER / 'execution-manifest.json',
          {'format': 'worker-execution-manifest', 'assignment_id': AID,
           'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
           'status': 'selected_cpu_construction_partial', 'cases': rows})
    print(json.dumps({'cases': CASES, 'manifest_sha256': sha(FOLDER / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
