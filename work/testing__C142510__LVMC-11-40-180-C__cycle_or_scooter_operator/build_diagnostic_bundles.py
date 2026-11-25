"""Build six exact synthetic sidewalk construction protocol bundles."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
CAMERAS = ['overview', 'approach', 'reference_corner', 'driver_reference']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('returned diagnostic file exceeds 2 MiB')


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    note = HERE / 'diagnostic-source-note.json'
    write(note, {'format': 'c142510-diagnostic-source-v1',
                 'source_kind': 'synthetic_diagnostic_fixture',
                 'accepted_original_source': False,
                 'physical_acceptance': False,
                 'case_ids': [row['case_id'] for row in plan['cases']]})
    entries = []
    for row in plan['cases']:
        cid = row['case_id']
        name = cid.removeprefix(AID + '__')
        if 'silent' in name:
            signal_frame = None
        elif 'late' in name:
            signal_frame = 400
        else:
            signal_frame = 100
        response = 'advance' if 'advance' in name else 'yield_brake'
        site = {'case_id': cid, 'source_kind': 'synthetic_diagnostic_fixture',
                'cell_id': 'C142510', 'actor': 'cycle_or_scooter_operator',
                'physical_surface_kind': 'sidewalk', 'sidewalk_connected': True,
                'map_sha256': hashlib.sha256(b'<OpenDRIVE synthetic sidewalk fixture/>').hexdigest(),
                'sidewalk_source_citation': 'synthetic CPU fixture only',
                'connected_route_citation': 'synthetic CPU fixture only',
                'rider_blueprint_sha256': sha(note),
                'pedestrian_blueprint_sha256': sha(note),
                'audible_emitter_source_sha256': sha(note),
                'microphone_source_sha256': sha(note),
                'rider_kind': row['rider_kind'],
                'sidewalk_id': 'SYNTHETIC_SIDEWALK',
                'rider_route_xyz_m': [[-4, 0, 0], [4, 0, 0]],
                'pedestrian_route_xyz_m': [[-1, 0, 0], [3, 0, 0]],
                'planned_signal_frame': signal_frame,
                'planned_rider_response': response}
        config = {'law_id': 'LVMC-11-40-180-C', 'cell_id': 'C142510',
                  'actor': 'cycle_or_scooter_operator', 'selected_case_id': cid,
                  'rate_hz': 20, 'duration_s': 45, 'required_atoms': [],
                  'source_packets': [], 'cameras': CAMERAS,
                  'case': {'case_id': cid, 'rider_kind': row['rider_kind'],
                           'signal_frame': signal_frame, 'rider_response': response}}
        description = {'channels': [
            {'name': 'sidewalk_body_history', 'unit': 'm, original frame',
             'method': 'joined rider and pedestrian full-body polygon histories at 20 Hz'},
            {'name': 'pedestrian_audio', 'unit': 'PCM16 waveform and emitter frame',
             'method': 'microphone onset joined to source-sealed rider emitter events'},
            {'name': 'rider_response', 'unit': 'm/s and brake state',
             'method': 'original rider speed/brake history through overtake'},
            {'name': 'camera_frame_identity', 'unit': 'frame ID',
             'method': 'four synchronized original camera streams at 20 Hz'}],
                       'limitations': ['Synthetic protocol check only; reviewed connected sidewalk and original audio absent.',
                                       'Right-of-way yielding, human audibility and legal outcome unresolved.']}
        files = {'runner.py': (HERE / 'diagnostic_runner.py').read_text(),
                 'native_overtake.py': (HERE / 'native_overtake.py').read_text(),
                 'tests/test_bundle.py': (HERE / 'diagnostic_bundle_test.py').read_text(),
                 'config.json': json.dumps(config, indent=2) + '\n',
                 'scene.json': json.dumps(site, indent=2) + '\n'}
        construction = {'law_id': 'LVMC-11-40-180-C', 'cell_id': 'C142510',
                        'actor': 'cycle_or_scooter_operator', 'case_id': cid,
                        'entrypoint': 'runner.py', 'diagnostic_only': True,
                        'recording_description': description,
                        'files': [{'path': key, 'content': value} for key, value in files.items()]}
        path = HERE / ('construction-diagnostic-' + name + '.json')
        write(path, construction)
        entries.append({'case_id': cid, 'kind': 'capability_research',
                        'construction': path.name, 'construction_sha256': sha(path),
                        'diagnostic_only': True})
    write(HERE / 'execution-manifest.diagnostic.json',
          {'format': 'worker-execution-manifest', 'assignment_id': AID,
           'status': 'synthetic_only_original_sidewalk_pending',
           'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
           'cases': entries})
    return len(entries)


if __name__ == '__main__':
    print('synthetic diagnostic bundles:', build())
