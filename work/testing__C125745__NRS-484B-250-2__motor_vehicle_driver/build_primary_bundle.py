"""Build one exact C125745 CPU diagnostic bundle from the authored Native code.

The site coordinates and source documents are synthetic schema fixtures. They
cannot establish a real median crossing or official stop sign.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / 'tests'))
from test_median_route_control import scene  # noqa: E402
from site_packet import SOURCE_CLAIMS  # noqa: E402

CASE = HERE.name + '__stop_ego_left_near_time'
MODULES = ('runner.py', 'native_pair.py', 'median_route_control.py',
           'stop_sign_control.py', 'capture_sources.py', 'camera_encoder.py',
           'site_packet.py', 'finalizer.py', 'simultaneous_entries.py')


def emit(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    from capture_sources import CAMERAS
    site = scene()
    site.update(format='worker-stop-median-site-review',
                review_status='reviewed_candidate', native_map_name='TownSynthetic',
                intersection_id=44, all_entrance_road_lanes=[[1, 1], [2, 1]],
                camera_poses={name: [0, 0, 8, 0, -25, 0] for name in CAMERAS},
                source_refs={}, source_documents={})
    for role, road, pose in (('ego', 1, [0, 0, 0, 0]),
                             ('other', 2, [15, -15, 0, 90])):
        site['approaches'][role]['road_id'] = road
        site['approaches'][role]['spawn_pose'] = pose
    for role, fields in SOURCE_CLAIMS.items():
        relative = 'review/' + role + '.json'
        document = {'format': 'worker-stop-median-site-source',
                    'source_role': role, 'review_basis': 'synthetic CPU schema fixture; no real-site review',
                    'reviewed_site_fields': {key: site[key] for key in fields}}
        path = HERE / relative
        emit(path, document)
        site['source_refs'][role] = relative
        site['source_documents'][role] = {'path': relative, 'sha256': sha(path)}
    emit(HERE / 'site.json', site)
    recording = {'channels': [{'name': 'entry_timing', 'unit': 'structured record',
                               'method': 'complete body crossing history joined to original Native frames',
                               'time_window': 'entire capture', 'reference_frame': 'original Native frame',
                               'uncertainty': 'legal approximate-time judgment unresolved',
                               'sampling_rate_hz': 20}],
                 'context_inputs': [{'name': 'entry_context', 'unit': 'structured record',
                                     'method': 'source-bound crossing and stop-sign context'}],
                 'limitations': ['Synthetic site; physical and legal acceptance unclaimed']}
    config = {'assignment_id': HERE.name, 'selected_case_id': CASE,
              'law_id': 'NRS-484B-250-2', 'cell_id': 'C125745',
              'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'frames': 900,
              'duration_s': 45, 'other_release_frame': 40,
              'required_atoms': ['ru.subject', 'ru.motor_vehicle', 'kin.position',
                                 'kin.velocity', 'kin.speed', 'st.intersection', 'rel.bearing'],
              'recording_description': recording,
              'site_packet': {'path': 'site.json', 'sha256': sha(HERE / 'site.json')},
              'physical_completion': {'criterion': 'intersection_clearance',
                                      'motion_source': 'crossing_history.jsonl',
                                      'body_key': 'ego.body_vertices_xy_m',
                                      'intersection_polygon_xy_m': site['crossing_polygon_xy_m'],
                                      'exit_axis': 0, 'exit_sign': 1,
                                      'minimum_progress_m': 0.25,
                                      'engineering_tolerances_not_legal': True}}
    emit(HERE / 'config.json', config)
    files = []
    for name in MODULES:
        source = HERE / name
        files.append({'path': name, 'source': str(source.relative_to(REPO)),
                      'content': source.read_text()})
    for path in sorted((HERE / 'review').glob('*.json')):
        files.append({'path': 'review/' + path.name, 'content': path.read_text()})
    for name in ('site.json', 'config.json'):
        source = HERE / name
        files.append({'path': name, 'source': str(source.relative_to(REPO)),
                      'content': source.read_text()})
    files.append({'path': 'tests/test_bundle.py',
                  'content': "import json, unittest\nfrom pathlib import Path\nfrom runner import load_config\nclass BundleTest(unittest.TestCase):\n def test_exact_materialized_config(self):\n  config, site = load_config(Path('config.json'))\n  self.assertEqual(config['selected_case_id'], '" + CASE + "')\n  self.assertFalse(site.get('physical_acceptance_claimed', False))\n"})
    construction = {'case_id': CASE, 'law_id': config['law_id'],
                    'cell_id': config['cell_id'], 'actor': config['actor'],
                    'entrypoint': 'runner.py', 'status': 'synthetic_diagnostic_only',
                    'recording_description': recording,
                    'measurement_plan': {'contract': 'measurement-contract.json',
                                         'source': 'retained original Native crossing, controller and frame sources'},
                    'static_checks': ['Exact case, reviewed-shape site packet and both Native lanes'],
                    'termination_rules': ['900 synchronized frames; seal only after encoder closure and restoration'],
                    'mechanisms': ['Stop-sign-governed two-vehicle Native routes and four original camera streams'],
                    'files': files}
    emit(HERE / 'construction.json', construction)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'cases': [{'case_id': CASE, 'kind': 'delivery',
                           'construction': 'construction.json',
                           'construction_sha256': sha(HERE / 'construction.json'),
                           'physical_risk': {'status': 'physical',
                                             'reason': 'Native stop-sign governance and measured entry timing may drift'},
                           'candidates': [],
                           'measurement_contract': 'measurement-contract.json',
                           'measurement_procedure': {'entrypoint': 'finalizer.py'},
                           'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                              'host_env_var': 'CARLA_HOST',
                                              'port_env_var': 'CARLA_PORT'}}],
                'status': 'partial_first_case_cpu_bundle'}
    emit(HERE / 'execution-manifest.json', manifest)
    return {'case_id': CASE, 'construction_sha256': manifest['cases'][0]['construction_sha256'],
            'site_basis': 'synthetic CPU schema fixture'}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
