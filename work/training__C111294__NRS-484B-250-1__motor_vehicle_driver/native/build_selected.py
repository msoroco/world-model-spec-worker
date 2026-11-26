"""Build exact two-highway priority constructions from checked requests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
REPO = PACKAGE.parents[1]
CASES = ('priority_yield', 'priority_intrusion')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
MODULES = ('build.py', 'check.py', 'capture.py', 'assemble_original.py',
           'process_original.py', 'saved.py')
CHANNELS = ('st.intersection', 'st.lane_enters', 'drv.approaching',
            'drv.entering_intersection', 'drv.arrival_order', 'drv.yields_to',
            'drv.in_intersection', 'dev.traffic_signal', 'dev.stop_sign',
            'dev.yield_sign', 'drv.turning', 'rel.oncoming')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build(suffix, candidate):
    if suffix not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown priority construction')
    cid = PACKAGE.name + '__' + suffix
    draft = HERE / 'drafts' / suffix / candidate
    cfg = json.loads((draft / 'config.json').read_text())
    cfg.update({'cell_id': 'C111294', 'actor': 'motor_vehicle_driver',
                'law_id': 'NRS-484B-250-1', 'required_atoms': [],
                'source_packets': [], 'selected_case_id': cid,
                'case': {'case_id': cid}, 'duration_s': 30,
                'supported_case_ids': [cid],
                'physical_completion': {'criterion': 'intersection_clearance',
                    'motion_source': 'crossing_history.jsonl',
                    'body_key': 'ego_vertices_m', 'exit_axis': 0,
                    'exit_sign': 1, 'minimum_progress_m': 8,
                    'completion_goal_method': 'Source-body crossing of intersection exit; engineering milestone, not legal outcome'},
                'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                    'height': 1080 if name == 'overview' else 720,
                    'fps': 20, 'fov_deg': 80,
                    'pose_strategy': 'fixed_crossroads_overview' if name == 'overview' else 'fixed_entry_reference'}
                    for name in ('overview', 'approach', 'reference_corner', 'driver_reference')],
                'status': 'selected_cpu_prepared_original_unverified'})
    description = {'channels': [{'name': name, 'unit': 'structured',
        'method': 'Source-joined original actor body, timing, road and reviewed control context',
        'sampling_rate_hz': 20, 'time_window': '600 frames / 30 s',
        'reference_frame': 'two-highway Native frame and intersection boundary',
        'uncertainty': 'Original device governance, turn intent, yielding and pixels require review'}
        for name in CHANNELS], 'context_inputs': [],
        'limitations': ['Authored entry requests do not establish original physical timing.',
            'Device and opposite-direction left-turn exclusions require original source review.',
            'No legal right-of-way outcome is assigned by the fixture.']}
    files = []
    for name in ('assignment-source.json', 'case-plan.json', 'crossroads.xodr',
                 'requested-tracks.jsonl'):
        files.append({'path': name, 'content': (draft / name).read_text()})
    files.append({'path': 'inputs/' + PACKAGE.name + '/assignment.json',
                  'content': (draft / 'assignment-source.json').read_text()})
    files.append({'path': 'work/' + PACKAGE.name + '/case-plan.json',
                  'content': (draft / 'case-plan.json').read_text()})
    files.append({'path': 'config.json', 'content': json.dumps(cfg, indent=2) + '\n'})
    for name in MODULES:
        source = HERE / name
        files.append({'path': 'work/' + PACKAGE.name + '/native/' + name,
                      'source': str(source.relative_to(REPO)),
                      'content': source.read_text()})
    for name in ('runner.py', 'finalize_selected.py'):
        source = HERE / name
        files.append({'path': 'runner.py' if name == 'runner.py' else 'finalize.py',
                      'source': str(source.relative_to(REPO)) if name == 'runner.py' else None,
                      'content': source.read_text().replace('__CASE__', cid)})
    test = HERE / 'tests/test_exact.py'
    files.append({'path': 'tests/test_exact.py',
                  'source': str(test.relative_to(REPO)), 'content': test.read_text()})
    construction = {'case_id': cid, 'law_id': 'NRS-484B-250-1',
        'cell_id': 'C111294', 'actor': 'motor_vehicle_driver',
        'status': 'selected_cpu_prepared_original_unverified',
        'entrypoint': 'runner.py', 'files': files,
        'measurement_plan': {'method': 'Source-body first entry, other presence at ego entry, and exclusion context',
            'duration_s': 30, 'source_observation_channels': list(CHANNELS)},
        'recording_description': description,
        'static_checks': ['distinct-highway source topology', '600-frame entry requests',
            'four synchronized camera plans'],
        'termination_rules': ['600 frames', 'encoder closure and world restoration'],
        'mechanisms': ['CARLA two-highway OpenDRIVE world', 'two physical vehicle actors',
            'source-joined 4-camera capture and original body history']}
    path = HERE / 'selected' / suffix / candidate / 'construction.json'
    put(path, construction)
    return {'case_id': cid, 'candidate_id': candidate,
            'construction': str(path.relative_to(PACKAGE)),
            'construction_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps([build(s, c) for s in CASES for c in CANDIDATES], indent=2))
