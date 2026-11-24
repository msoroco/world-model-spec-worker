"""Bind the first unselected LVMC primary to an exact offline bundle."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__probe_1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cameras = [{'name': name, 'width': width, 'height': height} for name, width, height in
               (('overview', 1920, 1080), ('approach', 1280, 720),
                ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))]
    config = {'case_id': CASE, 'selected_case_id': CASE, 'supported_case_ids': [CASE],
              'law_id': 'LVMC-11-12-070-B', 'cell_id': 'C111294',
              'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'duration_s': 30,
              'cameras': cameras, 'required_atoms': [], 'source_packets': [],
              'case': {'case_id': CASE}, 'status': 'unselected_native_draft',
              'recording_description': {'channels': [
                  {'name': 'through_body_pose', 'unit': 'structured'},
                  {'name': 'entrant_body_pose', 'unit': 'structured'},
                  {'name': 'frame_join', 'unit': 'structured'}],
                  'limitations': ['Through-highway designation and first lawful yield need original physical review']}}
    runtime_sha = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': HERE.name, 'runtime_manifest_sha256': runtime_sha,
                'status': 'draft_not_selected', 'cases': []}
    for index in (1, 2):
        case = HERE.name + f'__probe_{index}'
        bundle = HERE / ('draft-primary' if index == 1 else 'draft-controlled')
        bundle.mkdir(exist_ok=True)
        current = dict(config)
        current['case_id'] = case
        current['selected_case_id'] = case
        current['supported_case_ids'] = [case]
        current['case'] = {'case_id': case}
        tests = '''import json\nfrom pathlib import Path\nimport unittest\nfrom runner import check, request\n\nclass ProposedCase(unittest.TestCase):\n    def test_exact_600_frame_four_camera_preflight(self):\n        value=check(json.loads(Path('config.json').read_text()))\n        self.assertTrue(value['passed'])\n        self.assertEqual(value['frames'],600)\n        self.assertEqual(len(value['cameras']),4)\n    def test_control_phases(self):\n        case=json.loads(Path('config.json').read_text())['case_id']\n        self.assertEqual(request(100,case)['through_target_speed_mps'],8)\n        self.assertEqual(request(200,case)['through_target_speed_mps'],0 if case.endswith('probe_1') else 8)\n        self.assertEqual(request(400,case)['through_target_speed_mps'],8)\n        with self.assertRaisesRegex(ValueError,'Frame'):request(600,case)\n    def test_wrong_identity_rejected(self):\n        config=json.loads(Path('config.json').read_text())\n        config['cell_id']='C999999'\n        with self.assertRaisesRegex(ValueError,'identity'):check(config)\n\nif __name__=='__main__':unittest.main()\n'''
        sources = {'runner.py': (HERE / 'native/runner.py').read_text(),
                   'measure_yield.py': (HERE / 'native/measure_yield.py').read_text(),
                   'road.xodr': (HERE / 'native/road.xodr').read_text(),
                   'config.json': json.dumps(current, indent=2) + '\n',
                   'tests/test_primary.py': tests}
        construction = {'case_id': case, 'law_id': current['law_id'], 'cell_id': current['cell_id'],
                        'actor': current['actor'], 'entrypoint': 'runner.py',
                        'files': [{'path': name, 'content': value} for name, value in sources.items()],
                        'recording_description': current['recording_description'],
                        'status': 'draft_not_selected'}
        path = bundle / 'construction.json'
        path.write_text(json.dumps(construction, indent=2) + '\n')
        manifest['cases'].append({'case_id': case, 'id': 'primary', 'kind': 'draft_not_selected',
                                  'construction': str(path.relative_to(HERE)),
                                  'construction_sha256': sha(path),
                                  'candidate_risk': {'status': 'physical',
                                      'reason': 'Native yield control, highway designation, visibility and entrant behavior unobserved'},
                                  'candidates': []})
    (HERE / 'draft-primary-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': manifest['cases'],
                      'manifest_sha256': sha(HERE / 'draft-primary-manifest.json')}, sort_keys=True))


if __name__ == '__main__':
    main()
