"""Bind exact current-runtime access-aisle constructions and source measurements."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'No person shall park a vehicle in an access aisle.'
CASES = ('controlled_1', 'controlled_2')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
OBS = ('st.parking_space', 'st.lane_marking', 'drv.standing_or_parked', 'rel.occupies', 'kin.extent')
SOURCES = ('road.xodr', 'aisle-context.json', 'premises-review.json',
           'aisle-designation-review.json', 'parking-review.json',
           'native-vehicle.jsonl', 'video_frames.jsonl', 'reference_corner.mkv')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def description():
    channels = []
    for name in OBS:
        channels.append({'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                         'method': 'original Native full-body trace and independent premise, aisle and parking review',
                         'time_window': '600 original frames', 'reference_frame': 'original Native frame and reviewed aisle coordinates',
                         'uncertainty': '50 ms sampling; legal designation and parking require independent source review',
                         'source': 'channels/' + name + '.jsonl'})
    return {'channels': channels, 'context_inputs': [],
            'limitations': ['Public access, official access-aisle designation and parking classification require separate original source reviews']}


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    dispositions = json.loads((HERE / 'case-plan.json').read_text())['requirement_dispositions']
    desc = description()
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial_source_bound_draft', 'cases': []}
    proposals = []
    for suffix in CASES:
        case_id = AID + '__' + suffix
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'supported_case_ids': [AID + '__' + s for s in CASES],
                  'candidate_id': 'primary', 'case': {'case_id': case_id},
                  'law_id': 'LVMC-11-52-136', 'cell_id': 'C200542', 'actor': 'motor_vehicle_driver',
                  'statutory_text': LAW, 'case_suffix': suffix, 'rate_hz': 20, 'duration_s': 30,
                  'required_atoms': [], 'source_packets': [],
                  'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280, 'height': 1080 if name == 'overview' else 720,
                               'pose_strategy': 'fixed premises original RGB', 'fov_deg': 85}
                              for name in CAMERAS],
                  'recording_description': desc, 'physical_acceptance_claimed': False,
                  'legal_verdict': None}
        files = [{'path': name, 'content': (HERE / 'runtime_native' / name).read_text()}
                 for name in ('runner.py', 'layout.py', 'measure_aisle.py', 'finalize.py', 'tests/test_native.py')]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        construction = {'case_id': case_id, 'law_id': config['law_id'],
                        'cell_id': config['cell_id'], 'actor': config['actor'],
                        'entrypoint': 'runner.py', 'files': files,
                        'recording_description': desc,
                        'measurement_plan': {'entrypoint': 'finalize.py', 'required_sources': list(SOURCES)},
                        'static_checks': ['OpenDRIVE public-premises surface with adjacent aisle and bay extents',
                                          '600 original frames at 20 Hz', 'four synchronized original RGB cameras'],
                        'termination_rules': ['600 frames', 'destroy owned actors and verify world restoration'],
                        'mechanisms': ['same premises, aisle, cameras and controller policy; only footprint overlap request changes'],
                        'status': 'cpu_draft_authority_unverified'}
        path = HERE / 'draft-exact' / suffix / 'primary/construction.json'
        write(path, construction)
        output_methods = (
            ('source_bound_aisle_parking', 'measured'),
            ('public_access_premises', 'premises_observation'),
            ('official_access_aisle', 'designation_observation'),
            ('parked_vehicle', 'parking_observation'),
            ('body_aisle_overlap', 'overlap_observation'))
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                    'requirements': [{'disposition_index': i, 'requirement': dispositions[i]['requirement'],
                                      'source': dispositions[i]['source'], 'output_key': key, 'method': method,
                                      'value_type': 'object', 'kind': 'measured' if i in (0, 4) else 'sourced_context',
                                      'inputs': list(SOURCES)}
                                     for i, (key, method) in enumerate(output_methods)],
                    'negative': {'remove': ['aisle-designation-review.json'],
                                 'error_contains': 'Missing required source: aisle-designation-review.json'}}
        write(path.parent.parent / 'measurement-contract.json', contract)
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
                                  'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
                                  'candidate_risk': {'status': 'physical',
                                                     'reason': 'The Native vehicle may stop short of the requested bay or aisle footprint; original body corners and speed must verify a parked position'},
                                  'candidates': [],
                                  'measurement_contract': str((path.parent.parent / 'measurement-contract.json').relative_to(HERE)),
                                  'fixture_recipe': 'work/' + AID + '/diagnostic-' + suffix + '-recipe.json',
                                  'measurement_procedure': {'entrypoint': 'finalize.py'},
                                  'preparation_status': 'incomplete'})
        proposals.append({'case_id': case_id, 'target_law_id': 'LVMC-11-52-136',
                          'target_type': 'controlled_attempt',
                          'rationale': 'Observe original stationary full-body footprint relative to separately reviewed official access aisle',
                          'variable_assignments': {'target_footprint_inside_aisle': {'kind': 'controller', 'value': suffix == 'controlled_2'}},
                          'unresolved_judgment_calls': ['public-access premises', 'official access-aisle designation', 'parked classification', 'legal outcome'],
                          'recording_description': desc,
                          'probe': {'primary_variable': 'stationary_overlap_samples',
                                    'comparison_or_standard': 'separately reviewed access-aisle bounds',
                                    'target_value_or_branch': 'outside' if suffix == 'controlled_1' else 'inside'}})
    write(HERE / 'draft-execution-manifest.json', manifest)
    write(HERE / 'proposals/cases.json', {'cell_id': 'C200542', 'actor': 'motor_vehicle_driver',
                                         'status': 'draft', 'sweeps_expanded': True, 'cases': proposals})
    print({row['case_id']: row['construction_sha256'] for row in manifest['cases']})


if __name__ == '__main__':
    main()
