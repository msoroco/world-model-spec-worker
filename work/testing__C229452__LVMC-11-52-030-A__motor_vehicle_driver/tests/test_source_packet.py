import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
for name in ('red_curb', 'source_packet'):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

import red_curb
import source_packet


class ReviewedPacketTests(unittest.TestCase):
    def make_packet(self, root, case):
        scene = dict(cell_id='C229452', actor='motor_vehicle_driver',
                     municipal_jurisdiction=True, red_curb_paint=True,
                     vehicle_kind=case.vehicle_kind, sign=case.sign,
                     activity=case.activity, purpose=case.purpose,
                     mail_dropbox_adjacent=True, curb_segment_id='curb-1',
                     parking_route_xy=[[0, 0], [3, 0]])
        sources = {}
        for field in source_packet.SOURCE_FIELDS:
            name = field + '.txt'
            (root / name).write_text(field + ' original reviewed source\n')
            digest = source_packet.sha(root / name)
            sources[field] = {'path': name, 'sha256': digest,
                              'citation': 'original local review: ' + field,
                              'reviewer': 'local-reviewer'}
            scene[field + '_source_sha256'] = digest
        packet = {
            'format': 'c229452-reviewed-red-curb-v1',
            'assignment_id': source_packet.ASSIGNMENT,
            'case_id': source_packet.ASSIGNMENT + '__' + case.name,
            'reviewer': 'local-reviewer', 'review_citation': 'local evidence register',
            'scene': scene, 'sources': sources,
            'camera_plan': {name: {'source_transform': 'original reviewed transform',
                                   'purpose': 'original vehicle, curb, sign and activity'}
                            for name in source_packet.CAMERAS},
            'native_adapter': {'sha256': 'a' * 64,
                               'citation': 'local reviewed adapter'},
        }
        path = root / 'packet.json'
        path.write_text(json.dumps(packet) + '\n')
        return path, packet

    def test_all_exact_cases_bind_original_source_bytes(self):
        scratch = Path.cwd() / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        for case in red_curb.CASES:
            with self.subTest(case=case.name), tempfile.TemporaryDirectory(dir=scratch) as tmp:
                path, _ = self.make_packet(Path(tmp), case)
                _, scene, chosen = source_packet.load_reviewed(
                    path, source_packet.ASSIGNMENT + '__' + case.name)
                self.assertEqual(chosen, case)
                self.assertEqual(scene['vehicle_kind'], case.vehicle_kind)

    def test_reject_changed_source_and_wrong_case(self):
        scratch = Path.cwd() / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            path, packet = self.make_packet(Path(tmp), red_curb.CASES[0])
            with self.assertRaisesRegex(ValueError, 'another case'):
                source_packet.load_reviewed(
                    path, source_packet.ASSIGNMENT + '__' + red_curb.CASES[1].name)
            (Path(tmp) / packet['sources']['red_curb']['path']).write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'bytes missing or changed'):
                source_packet.load_reviewed(path, packet['case_id'])

    def test_reject_unreviewed_camera_and_adapter(self):
        scratch = Path.cwd() / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            path, packet = self.make_packet(Path(tmp), red_curb.CASES[0])
            del packet['camera_plan']['overview']['source_transform']
            path.write_text(json.dumps(packet) + '\n')
            with self.assertRaisesRegex(ValueError, 'four-camera'):
                source_packet.load_reviewed(path, packet['case_id'])
            adapter = Path(tmp) / 'adapter.py'
            adapter.write_text('pass\n')
            with self.assertRaisesRegex(ValueError, 'bytes changed'):
                source_packet.checked_adapter(adapter, packet)


if __name__ == '__main__':
    unittest.main()
