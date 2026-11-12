"""Materialize the first case's CPU diagnostic bundle.

The site packet is synthetic and proves only the exact offline entrypoint path.
It makes no physical or statutory site claim.
"""
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASE = 'testing__C125697__NRS-484B-250-2__motor_vehicle_driver__off_ego_left_near_time'
CODE = ('runner.py', 'native_pair.py', 'controlled_pair.py', 'route_control.py',
        'signal_control.py', 'camera_setup.py', 'camera_encoder.py',
        'capture_sources.py', 'site_packet.py', 'finalizer.py',
        'simultaneous_entries.py')


def serialized(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    spec = importlib.util.spec_from_file_location('test_runner', HERE/'tests/test_runner.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = module.config()
    config['required_atoms'] = [
        'ru.subject', 'ru.motor_vehicle', 'kin.position', 'kin.velocity',
        'kin.speed', 'st.intersection', 'rel.bearing',
    ]
    config['recording_description'] = {
        'channels': [
            {'name': 'entry_timing', 'unit': 'structured record',
             'method': 'complete body crossing history joined to original frames',
             'time_window': 'entire capture', 'reference_frame': 'original Native frame',
             'uncertainty': 'legal approximate-time judgment unresolved', 'sampling_rate_hz': 20},
        ],
        'context_inputs': [
            {'name': 'entry_context', 'unit': 'structured record',
             'method': 'source-bound crossing and approach packet'},
        ],
        'limitations': ['Synthetic site; no physical or statutory acceptance'],
    }
    with tempfile.TemporaryDirectory() as temporary:
        site_dir = Path(temporary)
        module.write_review(site_dir, config)
        packet_files = [
            {'path': path.name, 'content': path.read_text()}
            for path in sorted(site_dir.iterdir()) if path.is_file()
        ]
    (HERE/'config.json').write_text(serialized(config))
    files = [{'path': name, 'source': str((HERE/name).relative_to(REPO)),
              'content': (HERE/name).read_text()} for name in CODE]
    files.extend(packet_files)
    files.extend([
        {'path': 'config.json', 'source': str((HERE/'config.json').relative_to(REPO)),
         'content': (HERE/'config.json').read_text()},
        {'path': 'tests/test_bundle.py', 'content':
         'import json, unittest\nfrom runner import validate_config\n'
         'class BundleTest(unittest.TestCase):\n'
         ' def test_exact_materialized_config(self):\n'
         '  config=json.load(open("config.json"))\n'
         '  self.assertEqual(validate_config(config)["selected_case_id"],'
         'config["selected_case_id"])\n'},
    ])
    construction = {
        'case_id': CASE, 'law_id': 'NRS-484B-250-2', 'cell_id': 'C125697',
        'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
        'recording_description': config['recording_description'], 'files': files,
        'status': 'synthetic_diagnostic_only',
        'measurement_plan': {'source': 'crossing_history.jsonl', 'saved_finalizer': 'finalizer.py'},
    }
    (HERE/'construction.json').write_text(serialized(construction))
    proposal = {
        'cell_id': 'C125697', 'actor': 'motor_vehicle_driver',
        'status': 'partial_synthetic_diagnostic',
        'cases': [{
            'case_id': CASE, 'target_law_id': 'NRS-484B-250-2',
            'target_type': 'boundary_probe',
            'rationale': 'Off-state ego-left entry timing at one synthetic crossing; physical site unverified',
            'variable_assignments': {
                'other_release_frame': {'kind': 'controller', 'value': 20, 'unit': 'frame'},
                'body_entry_time_delta_s': {'kind': 'subject_behavior', 'value': None, 'unit': 's'},
                'official_device_status': {'kind': 'world_setup', 'value': 'Off commanded; physical state unverified', 'unit': 'categorical'},
            },
            'unresolved_judgment_calls': ['approximately the same time',
                                          'official traffic-control devices',
                                          'yield the right-of-way'],
            'recording_description': config['recording_description'],
            'paired_probe_id': 'c125697-relative-right-side',
            'deliberate_differences': [],
            'probe': {'primary_variable': 'other_release_frame',
                      'comparison_or_standard': 'original complete-body entry timing; no legal cutoff',
                      'target_value_or_branch': 'off_ego_left_near_time'},
        }],
    }
    (HERE/'proposals').mkdir(exist_ok=True)
    (HERE/'proposals/cases.json').write_text(serialized(proposal))
    manifest = {
        'format': 'worker-execution-manifest',
        'assignment_id': HERE.name,
        'runtime_manifest_sha256': sha(REPO/'runtime/SOURCE-MANIFEST.json'),
        'cases': [{
            'case_id': CASE, 'kind': 'delivery', 'construction': 'construction.json',
            'construction_sha256': sha(HERE/'construction.json'),
            'measurement_procedure': {'entrypoint': 'finalizer.py'},
            'measurement_contract': 'measurement-contract.json',
            'fixture_recipe': str((HERE/'diagnostic-recipe.json').relative_to(REPO)),
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
        }],
        'status': 'partial_first_case_diagnostic',
    }
    (HERE/'execution-manifest.json').write_text(serialized(manifest))
    return manifest


if __name__ == '__main__':
    print(serialized(build()), end='')
