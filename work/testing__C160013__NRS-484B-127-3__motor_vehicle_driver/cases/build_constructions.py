"""Build exact C160013 inline diagnostic constructions from current sources.

Diagnostic site content is deliberately unreviewed and cannot start Native capture.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT = 'testing__C160013__NRS-484B-127-3__motor_vehicle_driver'
FILES = ('caravan_native.py', 'caravan_capture.py', 'caravan_control.py',
         'caravan_entry.py', 'caravan_construction.py', 'caravan_cameras.py',
         'caravan_video.py', 'caravan_spacing.py', 'caravan_saved.py', 'finalizer.py')
CASES = (('entrant_can_occupy_gap', 10, 'occupy'),
         ('entrant_cannot_occupy_gap', 3, 'stop_before'))
CHANNELS = (
    ('caravan_member_bodies', 'polygon metres', 'original Native complete bodies'),
    ('entering_vehicle_body', 'polygon metres', 'original Native complete body'),
    ('inter_body_opening', 'metres', 'projected complete-body edges on sourced highway'),
    ('entrant_gap_occupancy', 'boolean', 'complete entrant body inside same-lane gap'),
    ('member_contact', 'boolean', 'original complete-body intersection'),
)


def _sha(data):
    return hashlib.sha256(data.encode()).hexdigest()


def _serialize(value):
    return json.dumps(value, indent=2, sort_keys=True) + '\n'


def build():
    output = []
    entries = []
    for suffix, separation, outcome in CASES:
        case_id = ASSIGNMENT + '__' + suffix
        sites = {}
        for key in ('business_district_source', 'caravan_membership_source',
                    'route_source', 'lane_source'):
            path = key + '.txt'
            content = 'Synthetic diagnostic context for ' + key + '; no original Native review.\n'
            sites[key] = {'path': path, 'sha256': _sha(content), 'content': content}
        packet = {
            'site_review_status': 'diagnostic_unreviewed',
            'reviewer': 'none', 'native_map_id': 'FixtureMap',
            'outside_business_district': True, 'caravan_or_motorcade': True,
            'highway_id': 44, 'road_id': 7,
            'road_forward_xy': [1, 0],
            'roadway_polygon_xy_m': [[0, -5], [80, -5], [80, 5], [0, 5]],
            'selected_gap_index': 0, 'target_speed_mps': 4,
            'target_lane_id': -1,
            'caravan_vehicles': [
                {'blueprint_id': 'vehicle.tesla.model3',
                 'transform': {'x': 10 + i * separation, 'y': 0, 'z': .5, 'yaw_deg': 0}}
                for i in range(3)],
            'entering_vehicle': {
                'blueprint_id': 'vehicle.tesla.model3',
                'transform': {'x': 15 if outcome == 'occupy' else 8,
                              'y': -3, 'z': .5, 'yaw_deg': 0}},
            'camera_transforms': {
                'overview': {'x': 20, 'y': 0, 'z': 30, 'yaw_deg': 0},
                'caravan_gap': {'x': 16, 'y': 4, 'z': 8, 'yaw_deg': -90},
                'entrant_approach': {'x': 7, 'y': -5, 'z': 6, 'yaw_deg': 35},
                'driver_reference': {'x': 1, 'y': 0, 'z': 1.6, 'yaw_deg': 0}},
            'required_atoms': ['kin.position', 'kin.heading', 'kin.velocity']}
        for key, source in sites.items():
            packet[key] = {'path': source['path'], 'sha256': source['sha256']}
        description = {
            'channels': [
                {'name': name, 'unit': unit, 'method': method,
                 'time_window': 'original 45-second Native capture',
                 'reference_frame': 'original Native frame',
                 'sampling_rate_hz': 20, 'uncertainty': 'between-frame motion unresolved'}
                for name, unit, method in CHANNELS],
            'context_inputs': [
                {'name': 'road_context', 'unit': 'structured record',
                 'method': 'source-hashed district, route, lane and caravan membership'}],
            'limitations': ['Statutory without-danger judgment has no supplied numeric cutoff.',
                            'Diagnostic site does not establish Native map or camera review.']}
        config = {'cell_id': 'C160013', 'law_id': 'NRS-484B-127-3',
                  'actor': 'motor_vehicle_driver', 'selected_case_id': case_id,
                  'supported_case_ids': [ASSIGNMENT + '__' + row[0] for row in CASES],
                  'required_atoms': packet['required_atoms'], 'source_packets': [],
                  'rate_hz': 20, 'duration_s': 45,
                  'target_speed_cap_mps': 4,
                  'recording_description': description,
                  'physical_completion': ({'criterion': 'caravan_entry',
                                           'motion_source': 'caravan_history.jsonl',
                                           'body_key': 'participants.subject.body_vertices_m',
                                           'context_sources': ['caravan_context.json'],
                                           'destination_lane': -1,
                                           'minimum_progress_m': .25} if outcome == 'occupy' else
                                          {'criterion': 'travel_progress',
                                           'motion_source': 'caravan_history.jsonl',
                                           'body_key': 'participants.entrant.body_vertices_m',
                                           'context_sources': ['caravan_context.json'],
                                           'minimum_progress_m': 2}),
                  'cameras': [{'name': name, 'width': width, 'height': height, 'fov_deg': 90}
                              for name, (width, height) in {
                                  'overview': (1920, 1080), 'caravan_gap': (1280, 720),
                                  'entrant_approach': (1280, 720),
                                  'driver_reference': (1280, 720)}.items()],
                  'case': {'case_id': case_id, 'recording_description': description}}
        source_files = [{'path': name, 'source': str((ROOT / name).relative_to(ROOT.parents[1])),
                         'content': (ROOT / name).read_text(encoding='utf-8')}
                        for name in FILES]
        source_files.append({'path': 'runner.py',
                             'source': str((ROOT / 'caravan_native.py').relative_to(ROOT.parents[1])),
                             'content': (ROOT / 'caravan_native.py').read_text(encoding='utf-8')})
        source_files += [{'path': 'config.json', 'content': _serialize(config)},
                         {'path': 'site_packet.json', 'content': _serialize(packet)}]
        source_files += [{'path': source['path'], 'content': source['content']}
                         for source in sites.values()]
        test = '''import json, unittest\nfrom pathlib import Path\nimport caravan_native as native\nfrom caravan_capture import validate_site\nclass Offline(unittest.TestCase):\n def test_exact_identity_and_unreviewed_site_guard(self):\n  root=Path(__file__).resolve().parents[1]\n  config=json.loads((root/'config.json').read_text())\n  assert config['selected_case_id']==%r\n  assert config['duration_s']==45 and config['rate_hz']==20\n  assert len(config['cameras'])==4\n  packet=json.loads((root/'site_packet.json').read_text())\n  assert packet['site_review_status']=='diagnostic_unreviewed'\n  with self.assertRaisesRegex(ValueError,'Reviewed Native caravan site required'):\n   validate_site(packet,root,packet['native_map_id'])\n  assert set(native.CASES)==set(config['supported_case_ids'])\nif __name__=='__main__': unittest.main()\n''' % case_id
        source_files.append({'path': 'tests/test_offline.py', 'content': test})
        proposal = {'case_id': case_id, 'law_id': 'NRS-484B-127-3',
                    'cell_id': 'C160013', 'actor': 'motor_vehicle_driver',
                    'entrypoint': 'runner.py',
                    'recording_description': description, 'files': source_files,
                    'status': 'diagnostic_draft',
                    'measurement_plan': {'source': 'caravan_history.jsonl',
                                         'method': 'source-hashed original-body occupancy'},
                    'static_checks': ['runner --check', 'source-hashed site packet',
                                      'three distinct caravan members and entrant'],
                    'termination_rules': ['45 seconds at 20 Hz; entrant tracks the selected waypoint'],
                    'mechanisms': {'entry_outcome': outcome,
                                   'diagnostic_member_spacing_m': separation,
                                   'note': 'Synthetic site is not reviewed Native authority.'}}
        path = ROOT / 'cases' / (suffix + '-construction.json')
        path.write_text(_serialize(proposal), encoding='utf-8')
        fallback = json.loads(_serialize(proposal))
        fallback_config = next(item for item in fallback['files'] if item['path'] == 'config.json')
        candidate_config = json.loads(fallback_config['content'])
        candidate_config['target_speed_cap_mps'] = 2.5
        fallback_config['content'] = _serialize(candidate_config)
        fallback['mechanisms']['target_speed_cap_mps'] = 2.5
        fallback['mechanisms']['fallback_reason'] = 'Lower common target speed after observed approach-control instability.'
        fallback_path = ROOT / 'cases' / (suffix + '-fallback1-construction.json')
        fallback_path.write_text(_serialize(fallback), encoding='utf-8')
        fallback_digest = hashlib.sha256(fallback_path.read_bytes()).hexdigest()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        output.append((case_id, str(path.relative_to(ROOT)),
                       digest))
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': str(path.relative_to(ROOT)),
                        'construction_sha256': digest,
                        'candidate_risk': {
                            'status': 'physical',
                            'reason': 'Entrant approach may contact a caravan member or require abrupt braking.'},
                        'candidates': [{'id': 'fallback1',
                                        'construction': str(fallback_path.relative_to(ROOT)),
                                        'construction_sha256': fallback_digest,
                                        'trigger': {'source': 'original Native per-frame control and body history',
                                                    'metric': 'entrant contact or emergency brake before gap approach',
                                                    'failure_condition': 'contact observed or abrupt full brake before planned merge'},
                                        'changed_knobs': ['target_speed_cap_mps: 4 to 2.5']}]})
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': hashlib.sha256(Path('runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
                'cases': entries,
                'comparisons': []}
    (ROOT / 'execution-manifest.json').write_text(_serialize(manifest), encoding='utf-8')
    return output


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
