import json
from pathlib import Path
import unittest
from runner import check, request

class ProposedCase(unittest.TestCase):
    def test_exact_600_frame_four_camera_preflight(self):
        value=check(json.loads(Path('config.json').read_text()))
        self.assertTrue(value['passed'])
        self.assertEqual(value['frames'],600)
        self.assertEqual(len(value['cameras']),4)
    def test_control_phases(self):
        case=json.loads(Path('config.json').read_text())['case_id']
        self.assertEqual(request(100,case)['through_target_speed_mps'],8)
        self.assertEqual(request(200,case)['through_target_speed_mps'],0 if case.endswith('probe_1') else 8)
        self.assertEqual(request(400,case)['through_target_speed_mps'],8)
        with self.assertRaisesRegex(ValueError,'Frame'):request(600,case)
    def test_wrong_identity_rejected(self):
        config=json.loads(Path('config.json').read_text())
        config['cell_id']='C999999'
        with self.assertRaisesRegex(ValueError,'identity'):check(config)

if __name__=='__main__':unittest.main()
