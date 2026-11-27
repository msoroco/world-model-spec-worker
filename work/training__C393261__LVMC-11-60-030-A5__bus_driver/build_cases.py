"""Build the two selected Native bus dwell proposals from one fixed terminus."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = 'LVMC-11-60-030-A5'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    files = [
        {'path': name, 'content': (HERE / 'native' / name).read_text()}
        for name in ('runner.py', 'geometry.py', 'measure.py', 'finalize.py', 'tests/test_native.py')
    ]
    entries = []
    for suffix, dwell in (('probe_01', 8.0), ('probe_02', 18.0)):
        case_id = HERE.name + '__' + suffix
        config = {
            'case_id': case_id, 'selected_case_id': case_id,
            'supported_case_ids': [HERE.name + '__probe_01', HERE.name + '__probe_02'],
            'candidate_id': 'primary', 'law_id': LAW, 'cell_id': 'C393261',
            'actor': 'bus_driver', 'rate_hz': 20, 'duration_s': 30,
            'required_atoms': [], 'source_packets': [], 'case': {'case_id': case_id},
            'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                         'height': 1080 if name == 'overview' else 720,
                         'pose_strategy': 'fixed terminus survey' if name != 'driver_reference' else 'attached bus chase',
                         'fov_deg': 85} for name in
                        ('overview', 'approach', 'reference_corner', 'driver_reference')],
            'recording_description': {
                'channels': [
                    {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                     'method': 'Original post-tick bus history joined to Native terminus survey and source-gated authority',
                     'time_window': '600 original frames',
                     'reference_frame': 'residential endpoint road 1 parking lane -2',
                     'uncertainty': 'authority, bus activity, physical sign pixels and 50 ms sampling remain reviewable'}
                    for name in ('ru.bus', 'st.curb_zone', 'dev.regulatory_sign',
                                 'drv.standing_or_parked', 'kin.time', 'rel.occupies',
                                 'drv.condition_in_effect')],
                'context_inputs': [{'name': 'designation_authority_source',
                                    'unit': 'structured',
                                    'method': 'Hash-verified original Section 11.60.010 designation matched to exact endpoint and applicable period'}],
                'limitations': ['Official designated period and establishing authority absent',
                                'Sign need not display designated duration',
                                'Actual bus activity and non-tour status require original review']},
            'physical_target': {'target_dwell_s': dwell,
                                'designation_comparison': 'unknown until original authority is sourced'},
        }
        proposal = {
            'case_id': case_id, 'law_id': LAW, 'cell_id': 'C393261',
            'actor': 'bus_driver', 'entrypoint': 'runner.py',
            'files': files + [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'}],
            'recording_description': config['recording_description'],
            'measurement_plan': {'entrypoint': 'measure.py',
                                 'required_sources': ['terminus-history.jsonl', 'terminus-context.json'],
                                 'designation_policy': 'unknown without applicable original authority'},
            'static_checks': ['200m residential road with parking lane -2',
                              'bus blueprint with terminus marker', 'four cameras and 600 original frames'],
            'termination_rules': ['600 original frames', 'restore world and destroy owned actors'],
            'mechanisms': ['Native parked interval measured from pose and velocity',
                           'only source-verified designated period may be compared'],
            'status': 'selected_cpu_construction_physical_unverified',
        }
        path = HERE / 'cases' / suffix / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2) + '\n')
        if suffix == 'probe_01':
            (HERE / 'construction.json').write_text(path.read_text())
            (HERE / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
            for name in ('runner.py', 'geometry.py', 'measure.py', 'finalize.py'):
                (HERE / name).write_text((HERE / 'native' / name).read_text())
            tests = HERE / 'tests'
            tests.mkdir(exist_ok=True)
            (tests / 'test_native.py').write_text((HERE / 'native/tests/test_native.py').read_text())
        contract = {
            'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [{'disposition_index': 0, 'requirement': LAW,
                'source': 'inputs/planning/focused-coverage-20261016-v1/coverage-witnesses.json',
                'kind': 'measured', 'method': 'measure_bus_dwell',
                'output_key': 'bus_dwell', 'value_type': 'object',
                'inputs': ['terminus-history.jsonl', 'terminus-context.json',
                           'terminus-review.json', 'video_frames.jsonl', 'trace.jsonl',
                           'road.xodr', 'capture/manifest.json',
                           *[view + '.mkv' for view in
                             ('overview', 'approach', 'reference_corner', 'driver_reference')]]}],
            'negative': {'remove': ['terminus-context.json'],
                         'error_contains': 'Missing required source: terminus-context.json'},
        }
        (path.parent / 'measurement-contract.json').write_text(json.dumps(contract, indent=2) + '\n')
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': str(path.relative_to(HERE)),
                        'construction_sha256': sha(path),
                        'candidate_risk': {'status': 'none',
                                           'reason': 'No supported engineering fallback before original bus motion; physical review is required'},
                        'candidates': [], 'delivery_readiness': 'incomplete',
                        'measurement_contract': f'cases/{suffix}/measurement-contract.json',
                        'measurement_procedure': {'entrypoint': 'finalize.py'},
                        'fixture_recipe': f'work/{HERE.name}/cases/{suffix}/recipe.json',
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                           'host_env_var': 'CARLA_HOST',
                                           'port_env_var': 'CARLA_PORT'},
                        'acquisition': {name: {'entrypoint': 'runner.py',
                            'method': 'Original Native bus history, map survey and source-gated authority',
                            'evidence': ['terminus-history.jsonl', 'terminus-context.json',
                                         'terminus-review.json', 'video_frames.jsonl']}
                            for name in ('ru.bus', 'st.curb_zone', 'dev.regulatory_sign',
                                         'drv.standing_or_parked', 'kin.time',
                                         'rel.occupies', 'drv.condition_in_effect')},
                        'offline': {}, 'compatibility': {}, 'negative': {},
                        'post_capture': {}, 'physical_preparation': {},
                        'delivery_acceptance': {}})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'partial', 'cases': entries}
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': [(e['case_id'], e['construction_sha256']) for e in entries]}))


if __name__ == '__main__':
    main()
