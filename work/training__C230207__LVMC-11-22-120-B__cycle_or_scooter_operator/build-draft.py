"""Build signed-bicycle roadway exact-case Native CPU draft."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = (HERE.name + '__probe_01', HERE.name + '__probe_02')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    entries = []
    for case in CASES:
      config = {'assignment_id': HERE.name, 'case_id': case, 'selected_case_id': case,
              'supported_case_ids': list(CASES),
              'candidate_id': 'primary', 'law_id': 'LVMC-11-22-120-B', 'cell_id': 'C230207',
              'actor': 'cycle_or_scooter_operator', 'rider_class': 'human_propelled_bicycle',
              'rate_hz': 20, 'duration_s': 30, 'required_atoms': [], 'source_packets': [],
              'case': {'case_id': case},
      'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                           'height': 1080 if name == 'overview' else 720,
                           'pose_strategy': 'fixed surveyed sign and rider corridor',
                           'fov_deg': 85} for name in
                          ('overview', 'approach', 'reference_corner', 'driver_reference')],
              'recording_description': {'channels': [
                  {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                   'method': 'original Native bicycle poses joined to sign and road readback',
                   'time_window': '600 frames', 'reference_frame': 'signed roadway',
                   'uncertainty': '50 ms sample spacing; sign face and city designation pending review'}
                  for name in ('dev.regulatory_sign', 'dev.governs', 'ru.bicycle',
                               'st.roadway', 'rel.occupies')],
                  'context_inputs': [],
                  'limitations': ['City Traffic Engineer designation unavailable in Native simulation',
                                  'Sign face and bicycle wheels require independent physical review']},
              'status': 'partial_cpu_draft'}
      files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
             for name in ('runner.py', 'geometry.py', 'measure.py', 'finalize.py', 'tests/test_native.py')]
      files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
      proposal = {'case_id': case, 'law_id': config['law_id'], 'cell_id': config['cell_id'],
                'actor': config['actor'], 'entrypoint': 'runner.py', 'files': files,
                'recording_description': config['recording_description'],
                'measurement_plan': {'entrypoint': 'finalize.py',
                                     'required_sources': ['video_frames.jsonl', 'bicycle-poses.jsonl', 'restriction-context.json'],
                                     'status': 'source_bound_cpu_draft'},
                'static_checks': ['authored 120m signed OpenDRIVE road',
                                  'four cameras, 600 original frames', 'Native sign/lane survey gate'],
                'termination_rules': ['600 original frames', 'restore world and destroy owned actors'],
                'mechanisms': ['bicycle travels on the ' + ('shoulder' if case.endswith('probe_01') else 'roadway') + ' beside the signed roadway',
                               'original actor pose and sign/readback context',
                               'no official designation claim'],
                'status': 'partial_native_execution_cpu_checked_physical_unverified'}
      path = HERE / 'draft-signed-roadway' / case.rsplit('__', 1)[-1] / 'primary/construction.json'
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text(json.dumps(proposal, indent=2) + '\n')
      entries.append({'case_id': case, 'kind': 'delivery',
                      'construction': str(path.relative_to(HERE)),
                      'construction_sha256': sha(path),
                      'candidate_risk': {'status': 'physical',
                                         'reason': 'Sign pixels and bicycle motion require Native review'},
                      'candidates': [], 'measurement_procedure': {'entrypoint': 'finalize.py'},
                      'measurement_contract': 'cases/' + case.rsplit('__', 1)[-1] + '/measurement-contract.json',
                      'fixture_recipe': 'work/' + HERE.name + '/cases/' + case.rsplit('__', 1)[-1] + '/recipe.json',
                      'delivery_readiness': 'incomplete'})
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
                'assignment_id': HERE.name,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial',
                'cases': entries}
    (HERE / 'draft-signed-roadway-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    cases_proposal = {'format': 'scenario-cases-proposal', 'cell_id': 'C230207',
        'actor': 'cycle_or_scooter_operator', 'status': 'draft', 'sweep_specs': [],
        'cases': [{'case_id': case, 'target_law_id': 'LVMC-11-22-120-B',
            'target_type': 'controlled_attempt',
            'rationale': 'Compare original human-propelled bicycle roadway use after the same sign with shoulder travel.',
            'variable_assignments': {'surface': 'shoulder' if case.endswith('probe_01') else 'roadway'},
            'unresolved_judgment_calls': ['City Traffic Engineer designation and sign adequacy',
                'physical sign legibility and rider bicycle subtype'],
            'recording_description': config['recording_description']} for case in CASES]}
    (HERE / 'proposals').mkdir(exist_ok=True)
    (HERE / 'proposals/cases.json').write_text(json.dumps(cases_proposal, indent=2) + '\n')
    print(json.dumps({'case_ids': list(CASES), 'construction_sha256': [e['construction_sha256'] for e in entries],
                      'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}))


if __name__ == '__main__':
    main()
