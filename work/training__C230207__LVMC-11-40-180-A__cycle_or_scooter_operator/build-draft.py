"""Build selected mounted-sidewalk Native CPU draft."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__controlled_2'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    config = {'case_id': CASE, 'selected_case_id': CASE, 'supported_case_ids': [CASE],
              'candidate_id': 'primary', 'law_id': 'LVMC-11-40-180-A', 'cell_id': 'C230207',
              'actor': 'cycle_or_scooter_operator', 'rider_class': 'human_propelled_bicycle',
              'rate_hz': 20, 'duration_s': 30, 'required_atoms': [], 'source_packets': [],
              'case': {'case_id': CASE},
              'cameras': [{'name': name, 'width': 1280, 'height': 720} for name in
                          ('overview', 'sign_approach', 'sign_face', 'sidewalk_use')],
              'recording_description': {'channels': [
                  {'name': 'cycle_pose', 'unit': 'structured', 'sampling_rate_hz': 20,
                   'method': 'original Native actor transform and velocity', 'time_window': '600 frames',
                   'reference_frame': 'Fremont Street sidewalk', 'uncertainty': '50 ms sample spacing'},
                  {'name': 'restriction_context', 'unit': 'structured', 'sampling_rate_hz': 20,
                   'method': 'OpenDRIVE signal and sidewalk readback', 'time_window': '600 frames',
                   'reference_frame': 'Main Street to Seventh Street',
                   'uncertainty': 'physical sign pixels and geographic identity unverified'}],
                  'limitations': ['Original actor blueprint does not prove human rider posture or wheel power',
                                  'Fremont/Main/Seventh geographic identity needs independent local review',
                                  'Sign posting is a distinct obligation, not a condition of rider prohibition']},
              'status': 'partial_cpu_draft'}
    files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
             for name in ('runner.py', 'geometry.py', 'measure.py', 'tests/test_native.py')]
    files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
    proposal = {'case_id': CASE, 'law_id': config['law_id'], 'cell_id': config['cell_id'],
                'actor': config['actor'], 'entrypoint': 'runner.py', 'files': files,
                'recording_description': config['recording_description'],
                'measurement_plan': {'entrypoint': 'measure.py',
                                     'required_sources': ['bicycle-poses.jsonl', 'restriction-context.json',
                                                          'video_frames.jsonl'],
                                     'status': 'source_bound_cpu_draft'},
                'static_checks': ['authored 160m Fremont OpenDRIVE road with 3m sidewalk lane',
                                  'three-class restriction sign', 'four cameras, 600 original frames',
                                  'Native sign/sidewalk survey gate'],
                'termination_rules': ['600 original frames', 'restore world and destroy owned actors'],
                'mechanisms': ['bicycle actor travels on named sidewalk segment',
                               'original actor pose/velocity and sign/readback context',
                               'no visual posture or geographic identity claim'],
                'status': 'partial_native_execution_cpu_checked_physical_unverified'}
    path = HERE / 'draft-mounted-sidewalk/mounted_sidewalk/primary/construction.json'
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
                                              'reason': 'Rider posture, wheel power, sidewalk and sign pixels need Native review'},
                           'candidates': [], 'measurement_procedure': {'entrypoint': 'measure.py'},
                           'delivery_readiness': 'incomplete'}]}
    (HERE / 'draft-mounted-sidewalk-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(path),
                      'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}))


if __name__ == '__main__':
    main()
