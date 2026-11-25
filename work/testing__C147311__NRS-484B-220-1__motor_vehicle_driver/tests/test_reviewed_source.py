import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reviewed_source import FIELDS, construct_reviewed, measure_reviewed, verify
from test_one_way_direction import Adapter, probe, rows, scene


class ReviewedSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = probe.CASES[0]
        self.scene = scene(self.case)
        bindings = {}
        for name in FIELDS:
            path = self.root / (name + '.txt')
            path.write_text('reviewed fixture ' + name)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.scene[name + '_source_sha256'] = digest
            bindings[name] = {'path': path.name, 'sha256': digest,
                              'citation': 'fixture ' + name, 'reviewer': 'fixture'}
        self.packet = {'format': 'c147311-reviewed-site-v1', 'review_status': 'reviewed',
                       'reviewer': 'fixture', 'diagnostic_fixture': False,
                       'scene': self.scene, 'source_bindings': bindings}
        self.path = self.root / 'site.json'
        self.write_packet()

    def write_packet(self):
        self.path.write_text(json.dumps(self.packet))

    def bound_rows(self):
        output = rows(self.case, self.scene)
        for row in output:
            for name in ('driver_control', 'lane_inventory', 'one_way_designation',
                         'sign_authority', 'sign_message', 'sign_orientation', 'sign_governance'):
                row[name + '_source_sha256'] = self.scene[name + '_source_sha256']
        return output

    def test_reopens_all_sources_before_construction_and_measurement(self):
        self.assertEqual(len(verify(self.path, self.case.name)['source_hashes']), len(FIELDS))
        constructed = construct_reviewed(Adapter(), self.path, self.case.name)
        measured = measure_reviewed(self.bound_rows(), self.path, self.case.name)
        self.assertEqual(constructed['site_sha256'], measured['site_sha256'])
        self.assertEqual(measured['actual_direction'], 'designated')

    def test_rejects_changed_source_and_diagnostic_packet(self):
        (self.root / 'sign_authority.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'bytes missing or changed'):
            verify(self.path, self.case.name)
        self.packet['diagnostic_fixture'] = True
        self.write_packet()
        with self.assertRaisesRegex(ValueError, 'original reviewed'):
            verify(self.path, self.case.name)

    def test_rejects_source_path_escape(self):
        self.packet['source_bindings']['sign_message']['path'] = '../outside'
        self.write_packet()
        with self.assertRaisesRegex(ValueError, 'source path invalid'):
            verify(self.path, self.case.name)

    def test_rejects_original_frame_source_relabel(self):
        output = self.bound_rows()
        output[20]['sign_message_source_sha256'] = 'a' * 64
        with self.assertRaisesRegex(ValueError, 'frame context differs'):
            measure_reviewed(output, self.path, self.case.name)
