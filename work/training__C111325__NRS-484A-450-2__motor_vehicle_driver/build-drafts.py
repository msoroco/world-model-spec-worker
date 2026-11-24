"""Package two unselected exact-window crosswalk-stop drafts."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cameras = [{'name': n, 'width': w, 'height': h} for n, w, h in
               (('overview', 1920, 1080), ('approach', 1280, 720),
                ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))]
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': HERE.name,
                'runtime_manifest_sha256': sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json'),
                'status': 'draft_not_selected', 'cases': []}
    tests = '''import json\nfrom pathlib import Path\nimport unittest\nfrom runner import check, request\n\nclass ProposedCase(unittest.TestCase):\n    def test_exact_window_and_cameras(self):\n        value=check(json.loads(Path('config.json').read_text()))\n        self.assertTrue(value['passed'])\n        self.assertEqual(value['frames'],600)\n        self.assertEqual(len(value['cameras']),4)\n    def test_requested_control(self):\n        case=json.loads(Path('config.json').read_text())['case_id']\n        self.assertEqual(request(140,case)['target_speed_mps'],0 if case.endswith('probe_1') else 4)\n        with self.assertRaisesRegex(ValueError,'Frame'):request(600,case)\n    def test_wrong_identity_rejected(self):\n        config=json.loads(Path('config.json').read_text())\n        config['cell_id']='C999999'\n        with self.assertRaisesRegex(ValueError,'identity'):check(config)\n\nif __name__=='__main__':unittest.main()\n'''
    for index in (1, 2):
        case = HERE.name + f'__probe_{index}'
        bundle = HERE / f'draft-probe-{index}'
        bundle.mkdir(exist_ok=True)
        config = {'case_id': case, 'selected_case_id': case, 'supported_case_ids': [case],
                  'law_id': 'NRS-484A-450-2', 'cell_id': 'C111325',
                  'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'duration_s': 30,
                  'cameras': cameras, 'required_atoms': [], 'source_packets': [],
                  'case': {'case_id': case}, 'status': 'unselected_native_draft',
                  'recording_description': {'channels': [
                      {'name': name, 'unit': unit, 'sampling_rate_hz': 20,
                       'method': 'Retained Native-shaped sample and frame join',
                       'time_window': 'entire 30 s / 600-frame attempt',
                       'reference_frame': 'original Native frame identity',
                       'uncertainty': '50 ms sampling; physical acquisition unverified'}
                      for name, unit in (('vehicle_body_pose', 'structured'),
                                         ('vehicle_speed', 'm/s'), ('frame_join', 'structured'))],
                      'context_inputs': [],
                      'limitations': ['Native capture, physical sign and crosswalk, and statutory branches unverified']}}
        config['mandatory_channels'] = [c['name'] for c in config['recording_description']['channels']]
        config['case']['recording_description'] = config['recording_description']
        sources = {'runner.py': (HERE / 'native/runner.py').read_text(),
                   'measure_stop.py': (HERE / 'native/measure_stop.py').read_text(),
                   'finalize.py': (HERE / 'native/finalize.py').read_text(),
                   'authored-road.xodr': (HERE / 'native/road.xodr').read_text(),
                   'config.json': json.dumps(config, indent=2) + '\n',
                   'tests/test_primary.py': tests}
        construction = {'case_id': case, 'law_id': config['law_id'],
                        'cell_id': config['cell_id'], 'actor': config['actor'],
                        'entrypoint': 'runner.py',
                        'files': [{'path': name, 'content': value} for name, value in sources.items()],
                        'recording_description': config['recording_description'],
                        'status': 'draft_not_selected'}
        path = bundle / 'construction.json'
        path.write_text(json.dumps(construction, indent=2) + '\n')
        manifest['cases'].append({'case_id': case, 'id': 'primary',
                                  'kind': 'draft_not_selected',
                                  'construction': str(path.relative_to(HERE)),
                                  'construction_sha256': sha(path),
                                  'candidate_risk': {'status': 'physical',
                                      'reason': 'Native stop control, sign, crosswalk and camera capture unobserved'},
                                  'candidates': []})
    path = HERE / 'draft-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(path), 'cases': manifest['cases']}, sort_keys=True))


if __name__ == '__main__':
    main()
