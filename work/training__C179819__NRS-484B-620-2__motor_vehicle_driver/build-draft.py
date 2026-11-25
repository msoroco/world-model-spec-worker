"""Bind exact signed-zone primary constructions and measurement contracts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'After the establishment of a speed zone and the installation of appropriate signs to control speed, it is unlawful for any person to drive a motor vehicle upon the road and in the speed zone in excess of the speed therein authorized.'
CASES = (('probe_01', 'below', 20), ('probe_02', 'at', 25), ('probe_03', 'above', 30))
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
OBSERVABLES = ('kin.speed', 'dev.speed_limit_sign', 'dev.zone_sign', 'drv.within_signed_zone',
               'dev.governs', 'rel.occupies', 'ru.motor_vehicle')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def description():
    channels = []
    for name in OBSERVABLES:
        channels.append({'name': name, 'unit': 'm/s' if name == 'kin.speed' else 'structured',
            'sampling_rate_hz': 20, 'method': 'original Native velocity' if name == 'kin.speed' else 'original route and separately reviewed zone/sign source',
            'time_window': '600 original frames', 'reference_frame': 'original Native frame and signed zone road axis',
            'uncertainty': '50 ms sampling; administrative and sign authority require independent review',
            'source': 'channels/' + name + '.jsonl'})
    return {'channels': channels, 'context_inputs': [],
        'limitations': ['Administrative zone establishment and installed-sign appropriateness require separate original source reviews']}


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    desc = description()
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
        'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
        'status': 'partial_source_bound_draft', 'cases': []}
    proposal_cases = []
    for suffix, kind, mph in CASES:
        case_id = AID + '__' + suffix
        config = {'case_id': case_id, 'selected_case_id': case_id,
            'supported_case_ids': [AID + '__' + s for s, _, _ in CASES],
            'candidate_id': 'primary', 'case': {'case_id': case_id},
            'law_id': 'NRS-484B-620-2', 'cell_id': 'C179819', 'actor': 'motor_vehicle_driver',
            'statutory_text': LAW, 'speed_case': kind, 'rate_hz': 20, 'duration_s': 30,
            'required_atoms': [], 'source_packets': [], 'cameras': [
                {'name': name, 'width': 1920 if name == 'overview' else 1280,
                 'height': 1080 if name == 'overview' else 720,
                 'pose_strategy': 'fixed roadside original RGB' if name in ('overview', 'reference_corner') else 'subject mounted original RGB',
                 'fov_deg': 90} for name in CAMERAS],
            'recording_description': desc, 'physical_acceptance_claimed': False,
            'legal_verdict': None}
        files = [{'path': name, 'content': (HERE / 'runtime_native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'controller.py', 'measure_zone.py', 'finalize.py', 'tests/test_native.py')]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        construction = {'case_id': case_id, 'law_id': config['law_id'],
            'cell_id': config['cell_id'], 'actor': config['actor'],
            'entrypoint': 'runner.py', 'files': files,
            'recording_description': desc,
            'measurement_plan': {'entrypoint': 'finalize.py', 'required_sources': [
                'road.xodr', 'zone-establishment.json', 'installed-sign-review.json',
                'actor-poses.jsonl', 'video_frames.jsonl', 'reference_corner.mkv']},
            'static_checks': ['800 m paved road with source-visible signed zone',
                '600 original frames at 20 Hz', 'four original RGB cameras'],
            'termination_rules': ['600 frames', 'destroy owned actors and verify world restoration'],
            'mechanisms': ['same road and sign; only controller speed request changes'],
            'status': 'cpu_draft_authority_unverified'}
        path = HERE / 'draft-exact' / suffix / 'primary/construction.json'
        write(path, construction)
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [{'disposition_index': 0, 'requirement': 'NRS-484B-620-2',
                'source': 'inputs/planning/focused-coverage-20261016-v1/coverage-witnesses.json',
                'output_key': 'source_bound_signed_zone_speed', 'method': 'source_bound_zone_measurement',
                'value_type': 'object', 'kind': 'measured', 'inputs': [
                    'road.xodr', 'zone-establishment.json', 'installed-sign-review.json',
                    'actor-poses.jsonl', 'reference_corner.mkv']}],
            'negative': {'remove': ['zone-establishment.json'],
                'error_contains': 'Missing required source: zone-establishment.json'}}
        write(path.parent.parent / 'measurement-contract.json', contract)
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical', 'reason': 'Original speed controller may undershoot on the signed-zone approach; local Native trace must verify a complete entry/exit and stable speed'},
            'candidates': [], 'measurement_contract': str((path.parent.parent/'measurement-contract.json').relative_to(HERE)),
            'fixture_recipe': 'work/' + AID + '/diagnostic-' + suffix + '-recipe.json',
            'measurement_procedure': {'entrypoint': 'finalize.py'}, 'preparation_status': 'incomplete'})
        proposal_cases.append({'case_id': case_id, 'target_law_id': 'NRS-484B-620-2',
            'target_type': 'boundary_probe',
            'rationale': 'Observe original velocity inside separately reviewed established and signed zone without assigning a legal label',
            'variable_assignments': {'controller_speed_request_mps': {'kind': 'controller', 'value': round(mph*.44704,6)}},
            'unresolved_judgment_calls': ['prior administrative establishment', 'appropriate installed signs', 'legal outcome'],
            'recording_description': desc,
            'probe': {'primary_variable': 'measured_speed_mph_in_zone', 'comparison_or_standard': 'source-reviewed authorized speed',
                'target_value_or_branch': kind}})
    write(HERE / 'draft-execution-manifest.json', manifest)
    write(HERE / 'proposals/cases.json', {'cell_id': 'C179819', 'actor': 'motor_vehicle_driver',
        'status': 'draft', 'sweeps_expanded': True, 'cases': proposal_cases})
    print({x['case_id']: x['construction_sha256'] for x in manifest['cases']})


if __name__ == '__main__':
    main()
