import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'saved_audit.py'
spec = importlib.util.spec_from_file_location('saved_audit', MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class SavedAuditTest(unittest.TestCase):
    def make(self, root):
        data = {'case_id': 'case', 'cell_id': 'C136559', 'law_id': 'NRS-484B-620-2',
                'map_source_sha256': 'map', 'zone_establishment_source_sha256': 'order',
                'zone_extent_source_sha256': 'extent', 'sign_instruction_source_sha256': 'sign',
                'camera_plan_sha256': 'cameras', 'ego_blueprint': 'car',
                'authorized_speed_mph': 25.0,
                'original_rows': [{'original_frame': i, 'original_time_s': i/20,
                                   'ego_id': 'ego', 'sign_readback_source_sha256': 'native-sign',
                                   'inside_zone': True, 'sign_installed': True,
                                   'actual_speed_mps': 11.0} for i in range(900)]}
        capture = Path(root)/'capture.json'
        seal = Path(root)/'seal.json'
        capture.write_text(json.dumps(data))
        seal.write_text(json.dumps({'case_id': 'case', 'capture_sha256': hashlib.sha256(capture.read_bytes()).hexdigest()}))
        return capture,seal,data

    def test_valid_full_capture(self):
        with tempfile.TemporaryDirectory() as root:
            capture,seal,_ = self.make(root)
            self.assertEqual(mod.audit(capture,seal,'case')['frame_count'],900)

    def test_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            capture,seal,_ = self.make(root)
            capture.write_text(capture.read_text()+' ')
            with self.assertRaisesRegex(ValueError,'seal mismatch'):
                mod.audit(capture,seal,'case')

    def test_missing_frame_rejected_after_reseal(self):
        with tempfile.TemporaryDirectory() as root:
            capture,seal,data = self.make(root)
            data['original_rows'][450]['original_frame']=451
            capture.write_text(json.dumps(data))
            seal.write_text(json.dumps({'case_id':'case','capture_sha256':hashlib.sha256(capture.read_bytes()).hexdigest()}))
            with self.assertRaisesRegex(ValueError,'frame gap'):
                mod.audit(capture,seal,'case')
