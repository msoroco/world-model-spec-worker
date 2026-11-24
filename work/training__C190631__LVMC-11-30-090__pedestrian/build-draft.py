"""Build source-bound roadway walking CPU draft from authored Native files."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__probe_02'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    config = {'case_id': CASE, 'selected_case_id': CASE,
              'supported_case_ids': [CASE], 'candidate_id': 'primary',
              'law_id': 'LVMC-11-30-090', 'cell_id': 'C190631', 'actor': 'pedestrian',
              'rate_hz': 20, 'duration_s': 30, 'required_atoms': [],
              'source_packets': [], 'case': {'case_id': CASE},
              'cameras': [{'name': name, 'width': 1280, 'height': 720}
                          for name in ('overview', 'along_roadway', 'sidewalk', 'pedestrian_close')],
              'recording_description': {'channels': [
                  {'name': 'pedestrian_pose', 'unit': 'structured', 'sampling_rate_hz': 20,
                   'method': 'original Native walker transform', 'time_window': '600 frames',
                   'reference_frame': 'authored overpass road', 'uncertainty': '50 ms sampling'},
                  {'name': 'surface_geometry', 'unit': 'polygon', 'sampling_rate_hz': 20,
                   'method': 'original Native map readback', 'time_window': '600 frames',
                   'reference_frame': 'authored overpass road', 'uncertainty': 'pending map readback'}],
                  'limitations': ['Native survey and walker/camera execution require CARLA verification']},
              'status': 'cpu_draft_not_delivery_prepared'}
    files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
             for name in ('runner.py', 'geometry.py', 'measure.py', 'tests/test_native.py')]
    files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
    proposal = {'case_id': CASE, 'law_id': config['law_id'], 'cell_id': config['cell_id'],
                'actor': config['actor'], 'entrypoint': 'runner.py', 'files': files,
                'recording_description': config['recording_description'],
                'measurement_plan': {'entrypoint': 'measure.py',
                                     'required_sources': ['pedestrian-poses.jsonl', 'surface-geometry.json'],
                                     'status': 'source_bound_cpu_draft'},
                'static_checks': ['100 m elevated OpenDRIVE with driving, shoulder and sidewalk lanes', 'four camera plan',
                                  '600-frame 20 Hz timing'],
                'termination_rules': ['600 original frames', 'restore world and destroy owned actors'],
                'mechanisms': ['walker follows adjacent roadway rather than sidewalk',
                               'original poses and surface geometry measured independently'],
                'status': 'partial_native_execution_cpu_checked_physical_unverified'}
    path = HERE / 'draft-roadway/roadway_walking/primary/construction.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proposal, indent=2) + '\n')
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
                'assignment_id': HERE.name,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial',
                'cases': [{'case_id': CASE, 'kind': 'delivery',
                           'construction': str(path.relative_to(HERE)),
                           'construction_sha256': sha(path),
                           'candidate_risk': {'status': 'physical',
                                              'reason': 'Overpass surface and walker path require Native readback'},
                           'candidates': [], 'measurement_procedure': {'entrypoint': 'measure.py'},
                           'delivery_readiness': 'incomplete'}]}
    (HERE / 'draft-roadway-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(path),
                      'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}))


if __name__ == '__main__':
    main()
