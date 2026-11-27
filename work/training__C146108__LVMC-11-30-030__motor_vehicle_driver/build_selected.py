"""Bind four exact source-gated crosswalk cases to their frozen assignment."""
import hashlib
import json
from pathlib import Path

from crosswalk_pass_scene import CASES, request, validate

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
MODULES = ('runner.py', 'native_construction.py', 'crosswalk_pass_scene.py',
           'measure_crosswalk_pass.py', 'prove_crosswalk_pass.py', 'finalize.py',
           'tests/test_selected.py')
ORDER = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def description(terms):
    return {'channels': [{'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': 'Original Native lead/ego/pedestrian body, crossing source and four-view time join',
             'time_window': 'all 600 frames including rear approach, lead rest and pedestrian crossing',
             'reference_frame': 'original CARLA frame and crossing geometry',
             'uncertainty': 'Crossing identity, lead stop purpose and legal outcome require original review'}
             for name in terms],
            'context_inputs': [{'name': name, 'unit': 'structured',
             'method': 'original Native source hash and independent review'}
             for name in ('native_map', 'crosswalk_reference', 'ego_body', 'lead_body',
                          'pedestrian_body', 'camera_manifest')],
            'limitations': ['A stopped lead near a crossing does not prove its purpose.',
                            'An authored unmarked junction reference does not prove original intersection geometry.',
                            'A requested pass does not prove physical passing or legal outcome.']}


def config(slug, terms):
    scene = request(slug)
    cid = AID + '__' + slug
    record = description(terms)
    return {'assignment_id': AID, 'law_id': 'LVMC-11-30-030', 'cell_id': 'C146108',
            'actor': 'motor_vehicle_driver', 'selected_case_id': cid,
            'case': {'case_id': cid, 'recording_description': record},
            'supported_case_ids': [AID + '__' + key for key in sorted(CASES)],
            'required_atoms': [], 'source_packets': [], 'rate_hz': 20,
            'duration_s': 30, 'frames': 600,
            'physical_completion': {'criterion': 'travel_progress', 'minimum_progress_m': 20.0,
                'engineering_tolerances_not_legal': True,
                'completion_goal_method': 'Requested ego travel from rear approach through hold or adjacent pass; measured from original Native body history'},
            'crosswalk_kind_requested': scene['crosswalk_kind_requested'],
            'pass_policy_requested': scene['controller']['policy'],
            'cameras': [{'name': item['name'], 'width': item['size'][0],
                         'height': item['size'][1], 'fps': 20, 'fov_deg': 80,
                         'pose_strategy': ('ego-attached' if item.get('attach_to_ego') else 'fixed') +
                                          ' original source view'}
                        for item in sorted(scene['cameras'], key=lambda item: ORDER.index(item['name']))],
            'recording_description': record,
            'physical_acceptance_claimed': False,
            'crosswalk_authority': 'unverified_original_source',
            'lead_stop_purpose': 'unassessed', 'legal_compliance': 'unassessed'}


def build(slug, plan, assignment, terms):
    scene = request(slug)
    validate(scene)
    if (assignment['law']['text'] != plan['source_law_text'] or
            assignment['cell']['layout'] != 'one_way_multilane' or
            assignment['cell']['maneuver'] != 'overtake' or
            assignment['cell']['control'] != 'other_vehicle'):
        raise ValueError('Frozen crosswalk law/cell differs')
    cid = AID + '__' + slug
    cfg = config(slug, terms)
    contract = {'format': 'worker-measurement-contract', 'case_id': cid,
                'status': 'selected_cpu_draft',
                'negative': {'remove': ['crosswalk-review.json'],
                             'error_contains': 'Missing required source: crosswalk-review.json'},
                'requirements': [{'disposition_index': i, 'requirement': item['requirement'],
                                  'source': item['source'], 'kind': 'measured',
                                  'method': 'measure_crosswalk',
                                  'output_key': 'crosswalk_pass_observation_' + str(i),
                                  'value_type': 'object',
                                  'inputs': ['road.xodr', 'crosswalk-review.json',
                                             'purpose-review.json', 'crosswalk_trace.jsonl',
                                             'video_frames.jsonl']}
                                 for i, item in enumerate(plan['requirement_dispositions'])
                                 if cid in item['case_ids']],
                'legal_compliance': 'unassessed'}
    contract_path = HERE / ('measurement-' + slug + '.json')
    put(contract_path, contract)
    files = [{'path': name, 'source': str((HERE / name).relative_to(REPO)),
              'content': (HERE / name).read_text()} for name in MODULES]
    frozen = REPO / 'inputs' / AID / 'assignment.json'
    files += [{'path': 'config.json', 'content': json.dumps(cfg, indent=2, ensure_ascii=False) + '\n'},
              {'path': 'inputs/' + AID + '/assignment.json',
               'source': 'inputs/' + AID + '/assignment.json', 'content': frozen.read_text()},
              {'path': 'work/' + AID + '/case-plan.json',
               'source': 'work/' + AID + '/case-plan.json',
               'content': (HERE / 'case-plan.json').read_text()}]
    construction = {'case_id': cid, 'law_id': 'LVMC-11-30-030', 'cell_id': 'C146108',
                    'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
                    'files': files, 'status': 'selected_cpu_prepared_original_unverified',
                    'recording_description': cfg['recording_description'],
                    'measurement_plan': {'method': 'source-bound crossing, lead stop purpose, pedestrian crossing and ego rear pass without legal judgment',
                                         'duration_s': 30, 'source_observation_channels': list(terms)},
                    'static_checks': ['one-way two-lane OpenDRIVE readback and crossing kind',
                                      'ego, stopped lead and crossing pedestrian actor creation',
                                      'four original 20 Hz cameras', '600-frame Native/Core/body/video joins'],
                    'termination_rules': ['600 original frames', 'encoder closure and world restore'],
                    'mechanisms': ['CARLA OpenDRIVE marked or unmarked intersection crossing',
                                   'rear ego approach and hold/pass policy',
                                   'source-joined four-view FFV1 and Native body telemetry']}
    path = HERE / 'selected' / slug / 'construction.json'
    put(path, construction)
    return {'case_id': cid, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'measurement_contract': contract_path.name,
            'fixture_recipe': 'work/' + AID + '/selected-recipe-' + slug + '.json',
            'recording_description': cfg['recording_description'],
            'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'},
            'candidate_risk': {'status': 'none',
                               'reason': 'Original intersection, pedestrian and ego trajectory need local Native review; no measured primary failure or justified fallback trigger yet'},
            'candidates': []}


def main():
    assignment = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    terms = [item['term'] for item in assignment['source_observation_terms']]
    entries = [build(slug, plan, assignment, terms) for slug in sorted(CASES)]
    batch = json.loads((REPO / 'batch.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'status': 'draft_incomplete_proofs',
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'physical_acceptance_claimed': False, 'cases': entries}
    put(HERE / 'draft-native-manifest.json', manifest)
    put(HERE / 'config.json', config('false', terms))
    put(HERE / 'construction.json', json.loads((HERE / entries[0]['construction']).read_text()))
    return {'cases': len(entries), 'manifest_sha256': sha(HERE / 'draft-native-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
