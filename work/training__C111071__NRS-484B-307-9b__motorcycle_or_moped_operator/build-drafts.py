"""Bind both unselected cycle variants to exact offline constructions."""
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
    tests = '''import json\nfrom pathlib import Path\nimport unittest\nfrom runner import check, request\n\nclass DraftCase(unittest.TestCase):\n    def test_exact_contract(self):\n        value=check(json.loads(Path('config.json').read_text()))\n        self.assertTrue(value['passed'])\n        self.assertEqual(value['frames'],600)\n        self.assertEqual(len(value['cameras']),4)\n    def test_observed_gate_request(self):\n        case=json.loads(Path('config.json').read_text())['case_id']\n        observation={'ego_face':'circular_red_green_left_arrow','cross_phase':'cross_green',\n                     'speed_mps':0,'front_to_stop_m':1,'entered_intersection':False,\n                     'pedestrians_in_crosswalk':False,'lawful_traffic_conflict':False,\n                     'completed_cycles':0}\n        self.assertEqual(request(100,case,observation)['brake'],1)\n        self.assertEqual(request(100,case,observation)['target_cycles'],2 if case.endswith('probe_1') else 1)\n        with self.assertRaisesRegex(ValueError,'Frame'):request(600,case,observation)\n    def test_wrong_identity(self):\n        config=json.loads(Path('config.json').read_text())\n        config['cell_id']='C999999'\n        with self.assertRaisesRegex(ValueError,'identity'):check(config)\n\nif __name__=='__main__':unittest.main()\n'''
    for index in (1, 2):
        case = HERE.name + f'__probe_{index}'
        bundle = HERE / f'draft-probe-{index}'
        bundle.mkdir(exist_ok=True)
        config = {'assignment_id': HERE.name, 'case_id': case,
                  'selected_case_id': case, 'supported_case_ids': [case],
                  'law_id': 'NRS-484B-307-9b', 'cell_id': 'C111071',
                  'actor': 'motorcycle_or_moped_operator', 'rate_hz': 20,
                  'duration_s': 30, 'case_variant': 'two_cycles' if index == 1 else 'one_cycle',
                  'cameras': cameras, 'required_atoms': [], 'source_packets': [],
                  'case': {'case_id': case}, 'status': 'unselected_native_draft',
                  'recording_description': {'channels': [
                      {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                       'method': 'Saved source join from original Native samples and frame map',
                       'time_window': 'entire 30 s / 600-frame attempt',
                       'reference_frame': 'original Native frame identity',
                       'uncertainty': '50 ms sampling; physical acquisition unverified'}
                      for name in ('ego_body_pose', 'signal_phase_readback', 'frame_join')],
                      'context_inputs': [],
                      'limitations': ['Physical signal causation, actor and four-camera acquisition unverified']}}
        config['mandatory_channels'] = [item['name'] for item in config['recording_description']['channels']]
        config['case']['recording_description'] = config['recording_description']
        sources = {'runner.py': (HERE / 'native/runner.py').read_text(),
                   'cycle_controller.py': (HERE / 'native/cycle_controller.py').read_text(),
                   'saved_measurement.py': (HERE / 'native/saved_measurement.py').read_text(),
                   'finalize.py': (HERE / 'native/finalize.py').read_text(),
                   'config.json': json.dumps(config, indent=2) + '\n',
                   'tests/test_draft.py': tests}
        construction = {'case_id': case, 'law_id': config['law_id'],
                        'cell_id': config['cell_id'], 'actor': config['actor'],
                        'entrypoint': 'runner.py',
                        'files': [{'path': n, 'content': value} for n, value in sources.items()],
                        'recording_description': config['recording_description'],
                        'status': 'draft_not_selected'}
        path = bundle / 'construction.json'
        path.write_text(json.dumps(construction, indent=2) + '\n')
        manifest['cases'].append({'case_id': case, 'id': 'primary',
                                  'kind': 'draft_not_selected',
                                  'construction': str(path.relative_to(HERE)),
                                  'construction_sha256': sha(path),
                                  'candidate_risk': {'status': 'physical',
                                      'reason': 'Native cycle timing, device readback and four cameras unverified'},
                                  'candidates': []})
    path = HERE / 'draft-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(path), 'cases': manifest['cases']}, sort_keys=True))


if __name__ == '__main__':
    main()
