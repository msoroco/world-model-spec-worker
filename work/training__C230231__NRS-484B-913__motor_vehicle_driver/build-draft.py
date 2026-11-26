"""Bind exact hose constructions and separate source-review measurements."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
CASES = ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
OBS = ('st.obstruction', 'rel.occupies', 'kin.path_length', 'st.highway',
       'ru.fire_apparatus', 'dev.human_direction', 'kin.velocity')
SOURCES = ('road.xodr', 'actor-sources.jsonl', 'camera-frames.jsonl',
           'hose-source.json', 'department-presence.json', 'communication-setup.json',
           'way-review.json', 'hose-review.json', 'command-review.json',
           'video_frames.jsonl', 'reference_corner.mkv')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def description():
    channels = []
    for name in OBS:
        channels.append({'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                         'method': 'original Native full-body trajectory and independent way, hose and command review',
                         'time_window': '600 original frames', 'reference_frame': 'original Native frame and reviewed hose geometry',
                         'uncertainty': '50 ms sampling; hose authority and consent require independent source review',
                         'source': 'channels/' + name + '.jsonl'})
    return {'channels': channels, 'context_inputs': [],
            'limitations': ['Hose identity/protection, way status, covered driver and command-official consent require independent original review']}


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    desc = description()
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial_source_bound_draft', 'cases': []}
    for suffix in CASES:
        case_id = AID + '__' + suffix
        crossing = suffix != 'witness_1'
        consent = suffix == 'exception_1_2'
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'supported_case_ids': [AID + '__' + s for s in CASES],
                  'candidate_id': 'primary', 'case': {'case_id': case_id},
                  'law_id': 'NRS-484B-913', 'cell_id': 'C230231', 'actor': 'motor_vehicle_driver',
                  'statutory_text': plan['source_law']['text'], 'case_suffix': suffix,
                  'cross_hose_requested': crossing, 'consent_record_requested': consent,
                  'rate_hz': 20, 'duration_s': 30,
                  'physical_completion': {'criterion': 'travel_progress', 'direction_xy': [1, 0],
                      'minimum_progress_m': 20, 'minimum_samples': 600,
                      'completion_goal_method': 'Authored 20 m travel milestone to inspect hose passage; not a statutory driven-over cutoff.'},
                  'required_atoms': [], 'source_packets': [],
                  'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                               'height': 1080 if name == 'overview' else 720,
                               'pose_strategy': 'fixed hose-way original RGB', 'fov_deg': 85}
                              for name in CAMERAS],
                  'recording_description': desc, 'physical_acceptance_claimed': False,
                  'legal_verdict': None}
        files = [{'path': name, 'content': (HERE / 'runtime_native' / name).read_text()}
                 for name in ('runner.py', 'layout.py', 'measure_hose.py', 'finalize.py', 'tests/test_native.py')]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        construction = {'case_id': case_id, 'law_id': config['law_id'],
                        'cell_id': config['cell_id'], 'actor': config['actor'],
                        'entrypoint': 'runner.py', 'files': files,
                        'recording_description': desc,
                        'measurement_plan': {'entrypoint': 'finalize.py', 'required_sources': list(SOURCES)},
                        'static_checks': ['OpenDRIVE way with drawn hose location and independent hose asset inventory',
                                          '600 original frames at 20 Hz', 'four synchronized original RGB cameras'],
                        'termination_rules': ['600 frames', 'destroy owned actors and verify world restoration'],
                        'mechanisms': ['Same way, hose location, cameras and speed policy; route offset or command communication differs by comparison'],
                        'status': 'cpu_draft_hose_authority_unverified'}
        path = HERE / 'draft-exact' / suffix / 'primary/construction.json'
        write(path, construction)
        outputs = (
            ('source_bound_hose_passage', 'measured'),
            ('qualifying_way_and_route', 'way_observation'),
            ('department_hose_purpose_protection', 'hose_observation'),
            ('covered_vehicle_and_driver', 'driver_observation'),
            ('original_vehicle_motion', 'motion_observation'),
            ('original_driven_hose_overlap', 'passage_observation'),
            ('command_official_communication', 'command_observation'))
        dispositions = plan['requirement_dispositions']
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                    'requirements': [{'disposition_index': i, 'requirement': dispositions[i]['requirement'],
                                      'source': dispositions[i]['source'], 'output_key': outputs[i][0],
                                      'method': outputs[i][1], 'value_type': 'object',
                                      'kind': 'measured' if i in (0, 4, 5) else 'sourced_context',
                                      'inputs': list(SOURCES)}
                                     for i in range(len(dispositions)) if case_id in dispositions[i]['case_ids']],
                    'negative': {'remove': ['hose-review.json'],
                                 'error_contains': 'Missing required source: hose-review.json'}}
        write(path.parent.parent / 'measurement-contract.json', contract)
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
                                  'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
                                  'candidate_risk': {'status': 'physical',
                                      'reason': 'Original vehicle may miss hose centerline or drawn diagnostic line may fail to represent a physical department hose; measured body and independent asset review must verify.'},
                                  'candidates': [],
                                  'measurement_contract': str((path.parent.parent / 'measurement-contract.json').relative_to(HERE)),
                                  'fixture_recipe': 'work/' + AID + '/diagnostic-' + suffix + '-recipe.json',
                                  'measurement_procedure': {'entrypoint': 'finalize.py'},
                                  'preparation_status': 'incomplete'})
    write(HERE / 'draft-execution-manifest.json', manifest)
    print({row['case_id']: row['construction_sha256'] for row in manifest['cases']})


if __name__ == '__main__':
    main()
