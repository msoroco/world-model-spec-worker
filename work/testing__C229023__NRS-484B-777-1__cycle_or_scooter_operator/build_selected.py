"""Materialize exact source-gated 777(1) Native bundles."""

import hashlib
import json
from pathlib import Path

from rightside import CASES


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'NRS-484B-777-1'
CAMERAS = [
    {'name': name, 'width': 1920 if index == 0 else 1280,
     'height': 1080 if index == 0 else 720, 'fov_deg': 90,
     'pose_strategy': 'reviewed cycle/right-roadway boundary and passing participant'}
    for index, name in enumerate(('overview', 'approach', 'reference_corner', 'driver_reference'))
]
CHANNELS = (
    ('right_edge_distance', 'm', 'cycle body right edge to reviewed roadway right boundary'),
    ('relative_station', 'm', 'cycle and target vehicle station across passing phase'),
    ('surface_clearance', 'm', 'original body surface clearance'),
    ('cycle_speed', 'm/s', 'original cycle speed and nearby traffic context'),
    ('other_vehicle_speed', 'm/s', 'original target vehicle speed'),
    ('right_access_width', 'm', 'original available right-side width'),
    ('lane_width', 'm', 'reviewed lane and cycle/vehicle body dimensions'),
    ('left_turn_preparation', 'boolean', 'source-sealed turn intent declaration and movement'),
    ('camera_frame_identity', 'original frame ID', 'four synchronized camera identities'),
)
RECORDING = {
    'channels': [{'name': name, 'unit': unit, 'method': method,
                  'sampling_rate_hz': 20, 'time_window': 'all 900 original frames',
                  'reference_frame': 'original Native roadway/world and frame map',
                  'uncertainty': 'body geometry and legal judgments require original review'}
                 for name, unit, method in CHANNELS],
    'context_inputs': [{'name': 'reviewed_roadway', 'unit': 'source record',
                        'method': 'source-hashed map, right boundary, lane/body dimensions and speed basis'}],
    'limitations': [
        'No numeric legal due-care, practicability, safety or commensurate-speed cutoff.',
        'Synthetic compatibility diagnostics do not establish original physical visibility.'],
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('returned exact bundle exceeds 2 MiB: ' + str(path))


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    ids = [case['case_id'] for case in plan['cases']]
    if ids != [AID + '__' + case.name for case in CASES]:
        raise ValueError('exact eight-case plan differs')
    source_files = ('runner.py', 'rightside.py', 'analysis.py', 'tests/test_bundle.py')
    entries = []
    for index, case in enumerate(plan['cases']):
        suffix = CASES[index].name
        config = {
            'assignment_id': AID, 'law_id': LAW, 'cell_id': 'C229023',
            'actor': 'cycle_or_scooter_operator', 'selected_case_id': case['case_id'],
            'supported_case_ids': ids, 'candidate_id': 'primary',
            'rate_hz': 20, 'duration_s': 45, 'frame_count': 900,
            'required_atoms': [], 'source_packets': [],
            'source_gate': 'reviewed_original_cycle_right_side_scene_required',
            'cameras': CAMERAS, 'case': {**case, 'recording_description': RECORDING,
                                       'disposition_indices': [index for index, item in enumerate(plan['requirement_dispositions'])
                                                               if case['case_id'] in item['case_ids']]},
        }
        config_path = HERE / ('config.json' if index == 0 else 'cases/' + suffix + '/config.json')
        write(config_path, config)
        files = []
        for name in source_files:
            path = HERE / name
            files.append({'path': name, 'source': str(path.relative_to(ROOT)),
                          'content': path.read_text()})
        files.append({'path': 'config.json', 'source': str(config_path.relative_to(ROOT)),
                      'content': config_path.read_text()})
        construction = {
            'law_id': LAW, 'cell_id': 'C229023', 'actor': 'cycle_or_scooter_operator',
            'case_id': case['case_id'], 'entrypoint': 'runner.py',
            'diagnostic_fixture': False, 'files': files,
            'measurement_plan': {'procedure': 'analysis.py',
                                 'source': 'reviewed original 900-frame right-side pass readback'},
            'recording_description': RECORDING,
            'static_checks': ['exact identity', 'reviewed original source hashes',
                              'right-side body geometry', 'four-camera original frame join'],
            'termination_rules': {'duration_s': 45,
                                  'missing_original_source': 'reject without accepted attempt'},
            'mechanisms': ['source-gated Native bicycle or scooter and target vehicle',
                           'reviewed passing routes and physical right-side impediment',
                           '20 Hz four-camera original capture and saved-only finalizer'],
        }
        cpath = HERE / ('construction.json' if index == 0 else 'cases/' + suffix + '/construction.json')
        write(cpath, construction)
        entries.append({
            'case_id': case['case_id'], 'kind': 'delivery',
            'construction': str(cpath.relative_to(HERE)), 'construction_sha256': sha(cpath),
            'measurement_procedure': {'entrypoint': 'analysis.py'},
            'source_gate': 'reviewed original cycle/right-side scene required',
            'candidate_risk': {'status': 'physical',
                               'reason': 'Original cycle spawn, pass phases, right-side feature or camera framing may miss the physical target.'},
            'candidates': [],
        })
        fallback_config = {**config, 'candidate_id': 'fallback1',
                           'pre_capture_settle_ticks': 10}
        fallback_text = json.dumps(fallback_config, indent=2, ensure_ascii=False) + '\n'
        fallback_files = [{**item, 'content': fallback_text, 'source': None}
                          if item['path'] == 'config.json' else item for item in files]
        fallback = {**construction, 'files': fallback_files}
        fallback_path = HERE / 'fallbacks' / suffix / 'construction.json'
        write(fallback_path, fallback)
        entries[-1]['candidates'] = [{
            'id': 'fallback1', 'construction': str(fallback_path.relative_to(HERE)),
            'construction_sha256': sha(fallback_path),
            'trigger': {'source': 'original 20 Hz rightside readback',
                        'metric': 'stable first captured frame and camera synchronization',
                        'failure_condition': 'first recorded frame lacks a settled cycle pose or one of four synchronized cameras'},
            'changed_knobs': ['pre_capture_settle_ticks: 0 to 10 before original recording'],
        }]
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'status': 'selected_proofs_pending',
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'cases': entries}
    write(HERE / 'execution-manifest.draft.json', manifest)
    return len(entries)


if __name__ == '__main__':
    print('exact right-side bundles:', build())
