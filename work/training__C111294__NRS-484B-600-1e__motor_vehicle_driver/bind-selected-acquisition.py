"""Bind every required speed observation to the selected Native readback."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATH = HERE / 'execution-manifest.json'

ACQUISITION = {
    'kin.speed': {
        'entrypoint': 'runner.py',
        'method': 'native_sample reads ego.get_velocity() in each Native frame; measure_speed computes its three-axis norm',
        'evidence': 'native_samples.jsonl ego_velocity_mps; speed-measurement.json peak_speed_mph',
    },
    'kin.velocity': {
        'entrypoint': 'runner.py',
        'method': 'native_sample reads ego.get_velocity() x, y, z from the captured actor',
        'evidence': 'native_samples.jsonl ego_velocity_mps',
    },
    'ego_pose': {
        'entrypoint': 'runner.py',
        'method': 'native_sample reads ego.get_transform() and world bounding-box vertices',
        'evidence': 'native_samples.jsonl ego_position_m, ego_heading_deg, ego_body_vertices_m',
    },
    'ego_speed': {
        'entrypoint': 'runner.py',
        'method': 'native_sample reads ego.get_velocity() in each Native frame',
        'evidence': 'native_samples.jsonl ego_velocity_mps',
    },
    'observed_speed': {
        'entrypoint': 'measure_speed.py',
        'method': 'measure computes peak and interval from saved three-axis Native velocity',
        'evidence': 'speed-measurement.json peak_speed_mph and interval_mph',
    },
    'other_vehicle_pose': {
        'entrypoint': 'runner.py',
        'method': 'native_sample reads other.get_transform() and world bounding-box vertices',
        'evidence': 'native_samples.jsonl other_position_m, other_heading_deg, other_body_vertices_m',
    },
}


def main():
    manifest = json.loads(PATH.read_text())
    for case in manifest['cases']:
        construction = json.loads((HERE / case['construction']).read_text())
        files = {entry['path']: entry['content'] for entry in construction['files']}
        config = json.loads(files['config.json'])
        required = set(config.get('required_atoms', ())) | {
            channel['name'] for channel in construction['recording_description']['channels']}
        if required != set(ACQUISITION) or not all(
                ACQUISITION[name]['entrypoint'] in files for name in required):
            raise ValueError('Acquisition map differs from selected construction')
        case['acquisition'] = ACQUISITION
    PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'observations_per_case': len(ACQUISITION),
                      'manifest_sha256': hashlib.sha256(PATH.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
