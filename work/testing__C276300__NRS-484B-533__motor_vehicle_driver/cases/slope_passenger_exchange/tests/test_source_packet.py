import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
for name in ('grade_stand', 'source_packet', 'runner', 'native_acquisition'):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

from source_packet import ASSIGNMENT, SOURCE_FIELDS, verify
from grade_stand import CASES


class SourcePacketTests(unittest.TestCase):
    def make_packet(self, folder, case=CASES[0]):
        from test_grade_stand import scene
        scene_data = scene(case)
        refs = {}
        for field in SOURCE_FIELDS:
            filename = field + '.txt'
            source = folder / filename
            source.write_text(field + ' diagnostic fixture only\n')
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            refs[field] = {'path': filename, 'sha256': digest}
            scene_data['map_opendrive_sha256' if field == 'map_opendrive'
                       else field + '_source_sha256'] = digest
        packet = {'assignment_id': ASSIGNMENT,
                  'case_id': ASSIGNMENT + '__' + case.name,
                  'source_kind': 'diagnostic_fixture',
                  'scene': scene_data, 'source_refs': refs}
        path = folder / 'source-packet.json'
        path.write_text(json.dumps(packet, indent=2) + '\n')
        return path, packet

    def test_exact_case_and_all_original_source_bytes(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
            root = Path(tmp)
            for case in CASES:
                path, packet = self.make_packet(root, case)
                self.assertEqual(verify(path, diagnostic_fixture=True)['case_id'],
                                 ASSIGNMENT + '__' + case.name)
            (root / 'front_wheels.txt').write_text('changed fixture\n')
            with self.assertRaisesRegex(ValueError, 'source bytes changed'):
                verify(path, diagnostic_fixture=True)

    def test_unreviewed_packet_and_path_escape_rejected(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
            root = Path(tmp)
            path, packet = self.make_packet(root)
            with self.assertRaisesRegex(ValueError, 'source kind is unreviewed'):
                verify(path)
            packet['source_refs']['engine']['path'] = '../outside.txt'
            path.write_text(json.dumps(packet) + '\n')
            with self.assertRaisesRegex(ValueError, 'source file missing'):
                verify(path, diagnostic_fixture=True)

    def test_lazy_runner_checks_selected_case_without_carla(self):
        import runner
        config, case_id = runner.check()
        self.assertIn(case_id, [ASSIGNMENT + '__' + case.name for case in CASES])
        self.assertEqual(case_id, config['selected_case_id'])
        self.assertEqual(config['duration_s'], 45)

    def test_native_operator_requires_mechanical_readback(self):
        from native_acquisition import REQUIRED_ADAPTER_METHODS, check_native_adapter
        class Operator:
            pass
        operator = Operator()
        for name in REQUIRED_ADAPTER_METHODS:
            if name != 'read_engine_ignition_and_rpm':
                setattr(operator, name, lambda *args: None)
        with self.assertRaisesRegex(ValueError, 'read_engine_ignition_and_rpm'):
            check_native_adapter(operator)
        setattr(operator, 'read_engine_ignition_and_rpm', lambda frame: None)
        check_native_adapter(operator)


if __name__ == '__main__':
    unittest.main()
