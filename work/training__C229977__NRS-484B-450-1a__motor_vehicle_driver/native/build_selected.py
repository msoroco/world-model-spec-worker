"""Materialize exact selected Native sidewalk cases and one risk fallback each."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parent.parent
ASSIGNMENT = 'training__C229977__NRS-484B-450-1a__motor_vehicle_driver'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


entries = []
disposition = json.loads((FOLDER / 'case-plan.json').read_text())['requirement_dispositions'][0]
measurement_contract = {
    'format': 'worker-measurement-contract',
    'requirements': [{
        'disposition_index': 0,
        'requirement': disposition['requirement'],
        'source': disposition['source'],
        'output_key': 'sidewalk_stop_occupancy',
        'method': 'sidewalk_stop',
        'value_type': 'object',
        'kind': 'measured',
        'inputs': ['vehicle-trace.jsonl', 'video_frames.jsonl',
                   'camera-frames.jsonl', 'map-packet.json',
                   'authority-context.json', 'native-road.xodr']}],
    'negative': {'remove': ['map-packet.json'],
                 'error_contains': 'Missing required source: map-packet.json'}}
dump(FOLDER / 'measurement-contract.json', measurement_contract)
for n in (1, 2):
    case_id = ASSIGNMENT + f'__probe_{n}'
    draft = json.loads((FOLDER / f'draft-probe-{n}' / 'construction.json').read_text())
    original_config = json.loads(next(item['content'] for item in draft['files']
                                      if item['path'] == 'config.json'))
    original_config['status'] = 'selected_native_construction'
    original_config['engineering'] = {'lateral_gain': 0.18,
                                      'brake_start_x_m': 31}
    original_config['source_packets'] = [
        'native-road.xodr', 'map-packet.json', 'vehicle-trace.jsonl',
        'video_frames.jsonl', 'authority-context.json']
    files = [
        {'path': 'runner.py', 'content': (HERE / 'selected_runner.py').read_text()},
        {'path': 'draft_runner.py', 'content': (HERE / 'draft_runner.py').read_text()},
        {'path': 'road.xodr', 'content': (HERE / 'draft_road.xodr').read_text()},
        {'path': 'finalize_sidewalk.py', 'content': (HERE / 'finalize_sidewalk.py').read_text()},
        {'path': 'sidewalk_occupancy.py', 'content': (HERE / 'sidewalk_occupancy.py').read_text()},
        {'path': 'measurement-contract.json', 'content': json.dumps(measurement_contract, sort_keys=True) + '\n'},
        {'path': 'config.json', 'content': json.dumps(original_config, sort_keys=True) + '\n'},
        {'path': 'tests/test_selected.py', 'content': (HERE / 'selected_test.py').read_text()},
    ]
    shared = {'case_id': case_id, 'law_id': 'NRS-484B-450-1a',
              'cell_id': 'C229977', 'actor': 'motor_vehicle_driver',
              'entrypoint': 'runner.py', 'recording_description': draft['recording_description'],
              'files': files, 'status': 'selected_native_construction'}
    primary_path = FOLDER / f'selected-probe-{n}' / 'construction.json'
    primary_path.parent.mkdir(exist_ok=True)
    dump(primary_path, shared)
    fallback_config = dict(original_config)
    fallback_config['engineering'] = {'lateral_gain': 0.24,
                                      'brake_start_x_m': 27}
    fallback = dict(shared)
    fallback['files'] = [dict(item, content=json.dumps(fallback_config, sort_keys=True) + '\n')
                         if item['path'] == 'config.json' else item for item in files]
    fallback_path = FOLDER / f'selected-probe-{n}' / 'fallback1.json'
    dump(fallback_path, fallback)
    entries.append({'case_id': case_id, 'kind': 'delivery',
        'construction': str(primary_path.relative_to(FOLDER)),
        'construction_sha256': sha(primary_path),
        'candidate_risk': {'status': 'physical',
            'reason': 'Native steering may miss sidewalk footprint or stop before target'},
        'candidates': [{'id': 'fallback1',
            'construction': str(fallback_path.relative_to(FOLDER)),
            'construction_sha256': sha(fallback_path),
            'trigger': {'source': 'original post-tick body/velocity and map packet',
                        'metric': 'rest_and_overlap_frames',
                        'failure_condition': 'requested contrast not physically realized'},
            'changed_knobs': ['lateral_gain 0.18 to 0.24',
                              'brake_start_x_m 31 to 27']} ]})
dump(FOLDER / 'selected-construction-manifest.json', {
    'format': 'worker-selected-construction-checkpoint',
    'assignment_id': ASSIGNMENT,
    'runtime_manifest_sha256': sha(REPO / 'runtime' / 'SOURCE-MANIFEST.json'),
    'status': 'offline_pending', 'cases': entries})
