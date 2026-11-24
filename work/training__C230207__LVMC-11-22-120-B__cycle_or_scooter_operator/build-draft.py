"""Build signed-bicycle roadway exact-case Native CPU draft."""
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
    config = {'case_id': CASE, 'selected_case_id': CASE, 'supported_case_ids': [CASE],
              'candidate_id': 'primary', 'law_id': 'LVMC-11-22-120-B', 'cell_id': 'C230207',
              'actor': 'cycle_or_scooter_operator', 'rider_class': 'human_propelled_bicycle',
              'rate_hz': 20, 'duration_s': 30, 'required_atoms': [], 'source_packets': [],
              'case': {'case_id': CASE},
              'cameras': [{'name': name, 'width': 1280, 'height': 720} for name in
                          ('overview', 'sign_approach', 'sign_face', 'roadway_use')],
              'recording_description': {'channels': [
                  {'name': 'bicycle_pose', 'unit': 'structured', 'sampling_rate_hz': 20,
                   'method': 'original Native actor transform', 'time_window': '600 frames',
                   'reference_frame': 'signed roadway', 'uncertainty': '50 ms sample spacing'},
                  {'name': 'restriction_context', 'unit': 'structured', 'sampling_rate_hz': 20,
                   'method': 'OpenDRIVE signal and roadway readback', 'time_window': '600 frames',
                   'reference_frame': 'governed road', 'uncertainty': 'physical sign pixels unverified'}],
                  'limitations': ['City Traffic Engineer designation unavailable in Native simulation',
                                  'Sign face and bicycle wheels require independent physical review']},
              'status': 'partial_cpu_draft'}
    files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
             for name in ('runner.py', 'geometry.py', 'measure.py', 'tests/test_native.py')]
    files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
    proposal = {'case_id': CASE, 'law_id': config['law_id'], 'cell_id': config['cell_id'],
                'actor': config['actor'], 'entrypoint': 'runner.py', 'files': files,
                'recording_description': config['recording_description'],
                'measurement_plan': {'entrypoint': 'measure.py',
                                     'required_sources': ['bicycle-poses.jsonl', 'restriction-context.json'],
                                     'status': 'source_bound_cpu_draft'},
                'static_checks': ['authored 120m signed OpenDRIVE road',
                                  'four cameras, 600 original frames', 'Native sign/lane survey gate'],
                'termination_rules': ['600 original frames', 'restore world and destroy owned actors'],
                'mechanisms': ['bicycle rides on signed roadway',
                               'original actor pose and sign/readback context',
                               'no official designation claim'],
                'status': 'partial_native_execution_cpu_checked_physical_unverified'}
    path = HERE / 'draft-signed-roadway/signed_bicycle_roadway/primary/construction.json'
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
                                              'reason': 'Sign pixels and bicycle behavior require Native review'},
                           'candidates': [], 'measurement_procedure': {'entrypoint': 'measure.py'},
                           'delivery_readiness': 'incomplete'}]}
    (HERE / 'draft-signed-roadway-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(path),
                      'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}))


if __name__ == '__main__':
    main()
