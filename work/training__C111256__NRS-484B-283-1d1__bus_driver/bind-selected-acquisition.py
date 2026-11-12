"""Bind every selected Walk observation to a bundled source implementation."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    sources = {
        'st.crosswalk': ('geometry.py', 'Authored marked crosswalk geometry and Native readback from road_geometry.json'),
        'kin.position': ('runner.py', 'Measured original bus pose/full body in trace.jsonl and capture/evidence.jsonl'),
        'dev.pedestrian_signal': ('finalize.py', 'Saved native_samples.jsonl Walk actor/display joined to independent original pixel and governance review'),
        'ru.pedestrian': ('measure_walk.py', 'Saved original pedestrian full-body and heading observations by Native frame'),
        'rel.occupies': ('measure_walk.py', 'Measured bus/pedestrian full-body overlap with source crosswalk geometry'),
        'drv.yields_to': ('finalize.py', 'Sampled source-joined bus/pedestrian crossing conflict; no legal yield verdict'),
        'kin.velocity': ('measure_walk.py', 'Measured Native bus speed with explicit provenance and trace/evidence join'),
        'native_body_pose_control': ('runner.py', 'Retained original bus and pedestrian body/control source rows'),
        'camera_frame_join': ('cameras.py', 'Four named source-camera videos joined by video_frames.jsonl')}
    for entry in manifest['cases']:
        construction = json.loads((HERE / entry['construction']).read_text())
        files = {item['path'] for item in construction['files']}
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        required = set(config.get('required_atoms', [])) | {
            item['name'] for item in construction['recording_description']['channels']}
        if required != set(sources) or any(script not in files for script, _ in sources.values()):
            raise ValueError('Walk acquisition lacks a selected implementation')
        entry['acquisition'] = {name: {
            'entrypoint': script, 'method': method,
            'evidence': 'Original Native source and independent Walk pixel review required; CPU fixture has synthetic_native_sample provenance'}
            for name, (script, method) in sources.items()}
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'selected_cases': len(manifest['cases']),
                      'channels_per_case': len(sources),
                      'manifest_sha256': sha(path), 'original_native_verified': False}))


if __name__ == '__main__':
    main()
