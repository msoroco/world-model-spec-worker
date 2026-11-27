"""Build four exact inline Native door/passing constructions."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SUFFIXES = ('board_overlap', 'board_clear', 'alight_overlap', 'alight_clear')
SOURCES = ('runner.py', 'controller.py', 'door_actuation.py', 'measure_door.py', 'finalize.py', 'tests/test_offline.py', 'native/door_interference.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def build():
    entries = []
    for suffix in SUFFIXES:
        case = ROOT.name + '__' + suffix
        config = ROOT / 'cases' / suffix / 'config.json'
        files = [{'path': name, 'content': (ROOT / name).read_text()} for name in SOURCES]
        files.append({'path': 'config.json', 'content': config.read_text()})
        construction = {
            'format': 'worker-inline-construction', 'case_id': case,
            'cell_id': 'C228817', 'actor': 'motor_vehicle_driver',
            'entrypoint': 'runner.py', 'files': files,
            'recording_description': json.loads(config.read_text())['recording_description'],
            'measurement_plan': {'procedure': 'source-hashed original Native door, transfer and passing traffic joins',
                'sources': ['native-door-trace.jsonl', 'video_frames.jsonl', 'door-pixel-review.json',
                            'original-scene-review.json', 'overview.mkv', 'approach.mkv',
                            'reference_corner.mkv', 'driver_reference.mkv'],
                'selected_measurements': ['door_open_frames', 'boarding_or_alighting',
                                          'moving_passing_traffic', 'passing_response_after_door_motion',
                                          'minimum_door_to_vehicle_gap_m'],
                'legal_interference': None},
            'static_checks': ['exact case and frozen-cell identity', '20 Hz and 600 frames',
                              'four original source cameras', 'door command distinct from observed motion',
                              'source-bound traffic side and transfer actor'],
            'termination_rules': ['retain 600 original Native frames',
                                  'close four source-video encoders',
                                  'restore world settings and destroy owned actors'],
            'mechanisms': ['source-bound road and traffic side', 'stationary loading vehicle',
                           'traffic-side door actuator', 'passing vehicle arrival schedule',
                           'board or alight passenger actor request', 'original four-view source capture'],
        }
        path = ROOT / 'cases' / suffix / 'construction.json'
        write(path, construction)
        entries.append({'case_id': case, 'kind': 'delivery',
                        'construction': str(path.relative_to(ROOT)),
                        'construction_sha256': sha(path),
                        'candidate_risk': {'status': 'physical',
                            'reason': 'Door motion, passenger transfer, and passing vehicle proximity require original CARLA readback'},
                        'candidates': [],
                        'measurement_procedure': {'entrypoint': 'finalize.py'},
                        'measurement_contract': 'native/selected-measurement-contract.json',
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                            'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                        'delivery_readiness': 'cpu_preparation_in_progress_original_capture_pending'})
    write(ROOT / 'construction.json', json.loads((ROOT / 'cases' / SUFFIXES[0] / 'construction.json').read_text()))
    write(ROOT / 'execution-manifest.json', {'format': 'worker-execution-manifest',
          'assignment_id': ROOT.name,
          'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
          'status': 'draft_cpu_preparation', 'cases': entries})
    return {'selected_cases': len(entries), 'construction_sha256': [e['construction_sha256'] for e in entries]}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
