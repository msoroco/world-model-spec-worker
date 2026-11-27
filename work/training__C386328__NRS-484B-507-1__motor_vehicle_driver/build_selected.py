"""Bind five exact source-gated freight-zone constructions to frozen inputs."""
import hashlib
import json
from pathlib import Path

from freight_scene import CASES, scene_request, validate_request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
MODULES = ('runner.py', 'native_construction.py', 'freight_scene.py',
           'measure_freight.py', 'finalize.py', 'tests/test_selected.py')
CHANNELS = ('st.curb_zone', 'dev.regulatory_sign', 'drv.condition_in_effect',
            'env.civil_time', 'drv.standing_or_parked', 'ru.commercial_motor_vehicle',
            'kin.extent', 'sig.door_open', 'ru.occupant_count', 'drv.approaching')
ORDER = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def description():
    return {'channels': [{'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': 'Original Native actor/sign/video source joined to independent full-interval review; unknown remains unknown',
             'time_window': 'all 600 frames including arrival, curb rest and departure',
             'reference_frame': 'original CARLA frame and civil signed hours',
             'uncertainty': 'Original authority, activity, identity and physical interference require independent review'}
             for name in CHANNELS],
            'context_inputs': [{'name': name, 'unit': 'structured',
             'method': 'original source hash and frame identity'}
             for name in ('native_map', 'freight_zone', 'sign_hours', 'ego_body',
                          'material_body', 'passenger_body', 'waiting_vehicle_body',
                          'camera_manifest')],
            'limitations': ['No statutory expeditiousness or temporary numeric cutoff is declared.',
                            'A waiting materials vehicle alone does not prove interference.',
                            'Authored sign and movement requests do not prove physical or legal results.']}


def config(slug):
    scene = scene_request(slug)
    cid = AID + '__' + slug
    record = description()
    return {'assignment_id': AID, 'law_id': 'NRS-484B-507-1', 'cell_id': 'C386328',
            'actor': 'motor_vehicle_driver', 'selected_case_id': cid,
            'case': {'case_id': cid, 'recording_description': record},
            'supported_case_ids': [AID + '__' + key for key in CASES],
            'required_atoms': [], 'source_packets': [], 'rate_hz': 20,
            'duration_s': 30, 'frames': 600,
            'physical_completion': {'criterion': 'travel_progress', 'minimum_progress_m': 20.0,
                'engineering_tolerances_not_legal': True,
                'completion_goal_method': 'Authored arrival and departure travel with original sampled motion review; independent of material or passenger legal exception'},
            'material_activity_requested': scene['material']['requested_activity'],
            'passenger_activity_requested': scene['passenger']['requested_activity'],
            'waiting_material_vehicle_requested': scene['material_transport_vehicle']['requested_waiting_to_enter'],
            'signed_hours_effective_requested': scene['civil_time']['requested_minute_local'] == 720,
            'cameras': [{'name': item['name'], 'width': item['size'][0],
                         'height': item['size'][1], 'fps': 20, 'fov_deg': 80,
                         'pose_strategy': ('ego-attached' if item.get('attach_to_vehicle') else 'fixed') +
                                          ' original source view'}
                        for item in sorted(scene['cameras'], key=lambda item: ORDER.index(item['name']))],
            'recording_description': record,
            'physical_acceptance_claimed': False,
            'freight_zone_authority': 'unverified_original_source',
            'expeditiousness': 'unassessed', 'interference': 'unassessed'}


def build(slug, plan, assignment):
    scene = scene_request(slug)
    validate_request(scene)
    if (assignment['law']['text'] != plan['source_law']['text'] or
            assignment['cell']['layout'] != 'one_way_road' or
            assignment['cell']['maneuver'] != 'park' or
            assignment['cell']['control'] != 'freight_loading_zone'):
        raise ValueError('frozen freight-zone law/cell differs')
    cid = AID + '__' + slug
    cfg = config(slug)
    contract = {'format': 'worker-measurement-contract', 'case_id': cid,
                'status': 'selected_cpu_draft',
                'negative': {'remove': ['zone-review.json'],
                             'error_contains': 'Missing required source: zone-review.json'},
                'requirements': [{'disposition_index': i, 'requirement': item['requirement'],
                                  'source': item['source'], 'kind': 'measured',
                                  'method': 'measure_freight_zone',
                                  'output_key': 'freight_zone_observation',
                                  'value_type': 'object',
                                  'inputs': ['road.xodr', 'zone-review.json',
                                             'activity-review.json', 'freight_trace.jsonl',
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
    construction = {'case_id': cid, 'law_id': 'NRS-484B-507-1', 'cell_id': 'C386328',
                    'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
                    'files': files, 'status': 'selected_cpu_prepared_original_unverified',
                    'recording_description': cfg['recording_description'],
                    'measurement_plan': {'method': 'source-bound zone occupancy, signed hours, material/passenger activity and waiting context without legal judgment',
                                         'duration_s': 30, 'source_observation_channels': list(CHANNELS)},
                    'static_checks': ['one-way OpenDRIVE curb and sign readback',
                                      'ego, material and conditional passenger/waiting actor creation',
                                      'four original 20 Hz cameras', '600-frame Native/Core/body/video joins'],
                    'termination_rules': ['600 original frames', 'encoder closure and world restore'],
                    'mechanisms': ['CARLA OpenDRIVE marked freight curb and sign',
                                   'ego, material, passenger and waiting vehicle requests',
                                   'source-joined four-view FFV1 and Native telemetry']}
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
            'candidate_risk': {'status': 'primary_unverified',
                               'reason': 'Original curb spawn, walker and waiting-materials-vehicle geometry require local Native physical review; no measured fallback trigger yet'},
            'candidates': []}


def main():
    assignment = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    entries = [build(slug, plan, assignment) for slug in CASES]
    batch = json.loads((REPO / 'batch.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'status': 'draft_incomplete_proofs',
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'physical_acceptance_claimed': False, 'cases': entries}
    put(HERE / 'draft-native-manifest.json', manifest)
    put(HERE / 'config.json', config('probe_1'))
    put(HERE / 'construction.json', json.loads((HERE / entries[0]['construction']).read_text()))
    return {'cases': len(entries), 'manifest_sha256': sha(HERE / 'draft-native-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
