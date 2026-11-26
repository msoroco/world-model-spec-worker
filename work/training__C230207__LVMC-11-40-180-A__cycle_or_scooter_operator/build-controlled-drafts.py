"""Bind both controlled Native programs to immutable CPU draft constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREFIX = HERE.name
SOURCE = HERE / 'draft-mounted-sidewalk/mounted_sidewalk/primary/construction.json'
MANIFEST = HERE / 'draft-mounted-sidewalk-manifest.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    template = json.loads(SOURCE.read_text())
    old_config = json.loads(next(f['content'] for f in template['files'] if f['path'] == 'config.json'))
    runtime = json.loads((ROOT / 'batch.json').read_text())['runtime']['source_manifest_sha256']
    cases = []
    for number, behavior, stem in ((1, 'walk_cycle', 'walk_cycle'),
                                   (2, 'mounted_sidewalk', 'mounted_sidewalk')):
        case_id = f'{PREFIX}__controlled_{number}'
        config = dict(old_config)
        config.update(case_id=case_id, selected_case_id=case_id,
                      supported_case_ids=[case_id], case={'case_id': case_id},
                      controlled_behavior=behavior,
                      bicycle_blueprint_id='vehicle.bh.crossbike',
                      status='partial_cpu_draft')
        config['recording_description'] = dict(config['recording_description'], context_inputs=[])
        config['cameras'] = [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                              'height': 1080 if name == 'overview' else 720}
                             for name in ('overview', 'approach', 'reference_corner', 'driver_reference')]
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                    'requirements': [{'disposition_index': 0,
                                      'requirement': 'LVMC-11-40-180-A',
                                      'source': 'LVMC 11.40.180(A)',
                                      'output_key': 'sidewalk_riding_observation',
                                      'method': 'sidewalk_riding_observation',
                                      'value_type': 'object', 'kind': 'measured',
                                      'inputs': ['bicycle-poses.jsonl', 'restriction-context.json',
                                                 'video_frames.jsonl', 'road.xodr', 'trace.jsonl']}],
                    'negative': {'remove': ['restriction-context.json'],
                                 'error_contains': 'Missing required source: restriction-context.json'}}
        contract_path = HERE / f'draft-mounted-sidewalk/{stem}/measurement-contract.json'
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        contract_path.write_text(json.dumps(contract, indent=2) + '\n')
        proposal = dict(template)
        proposal.update(case_id=case_id, entrypoint='runner.py',
                        run_arguments=['--behavior', behavior],
                        recording_description=config['recording_description'],
                        status='partial_native_execution_cpu_checked_physical_unverified')
        proposal['files'] = [
            {'path': name, 'content': (HERE / 'native' / name).read_text()}
            for name in ('runner.py', 'geometry.py', 'measure.py', 'finalize.py', 'tests/test_native.py')]
        proposal['files'].append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        proposal['files'].append({'path': 'measurement-contract.json',
                                  'content': json.dumps(contract, indent=2) + '\n'})
        proposal['measurement_plan'] = {
            'entrypoint': 'finalize.py',
            'required_sources': ['bicycle-poses.jsonl', 'restriction-context.json',
                                 'video_frames.jsonl', 'trace.jsonl', 'road.xodr'],
            'operator_source_required': behavior == 'walk_cycle',
            'posture_visual_review_required': True,
            'status': 'source_bound_cpu_draft'}
        proposal['mechanisms'] = [
            'one cycle travels on surveyed Fremont sidewalk for 600 synchronized frames',
            ('independent walking operator alongside cycle, with original actor association, '
             'position and velocity sources' if behavior == 'walk_cycle' else
             'cycle model with original pose and velocity; visual mounted posture remains unverified'),
            'original sign/sidewalk survey; geographic identity and sign pixels require review']
        path = HERE / f'draft-mounted-sidewalk/{stem}/primary/construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2) + '\n')
        alternate_config = dict(config, bicycle_blueprint_id='vehicle.diamondback.century',
                                candidate_id='fallback1')
        alternate = json.loads(json.dumps(proposal))
        alternate['candidate_id'] = 'fallback1'
        for item in alternate['files']:
            if item['path'] == 'config.json':
                item['content'] = json.dumps(alternate_config, indent=2) + '\n'
        alternate_path = HERE / f'draft-mounted-sidewalk/{stem}/fallback1/construction.json'
        alternate_path.parent.mkdir(parents=True, exist_ok=True)
        alternate_path.write_text(json.dumps(alternate, indent=2) + '\n')
        cases.append({'case_id': case_id, 'kind': 'delivery',
                      'construction': str(path.relative_to(HERE)),
                      'construction_sha256': digest(path),
                      'measurement_contract': str(contract_path.relative_to(HERE)),
                      'fixture_recipe': str((HERE / f'diagnostic-recipe-{stem}.json').relative_to(ROOT)),
                      'candidate_risk': {
                          'status': 'physical',
                          'reason': 'Rider posture, cycle model, sidewalk, sign pixels and named geography need local Native review'},
                      'candidates': [{
                          'id': 'fallback1',
                          'construction': str(alternate_path.relative_to(HERE)),
                          'construction_sha256': digest(alternate_path),
                          'trigger': {'source': 'fremont-original-review.json',
                                      'metric': 'integral rider or unreadable cycle posture',
                                      'failure_condition': 'primary bicycle model prevents independent rider posture review'},
                          'changed_knobs': ['bicycle_blueprint_id: vehicle.diamondback.century'],
                          'status': 'cpu_draft_unverified_physical'}],
                      'measurement_procedure': {'entrypoint': 'finalize.py'},
                      'delivery_readiness': 'incomplete'})
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
                'assignment_id': PREFIX, 'runtime_manifest_sha256': runtime,
                'status': 'partial', 'cases': cases}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    return {'cases': [{'case_id': c['case_id'], 'construction_sha256': c['construction_sha256']}
                      for c in cases], 'runtime_manifest_sha256': runtime}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
