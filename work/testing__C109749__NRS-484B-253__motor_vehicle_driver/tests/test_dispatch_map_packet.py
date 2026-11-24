"""Pinned local dispatcher supplies no --map-packet option."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_runner(name):
    path = ROOT / name
    spec = importlib.util.spec_from_file_location(name.removesuffix('.py'), path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict('sys.modules', {'construction': types.SimpleNamespace(build=lambda *_: {})}):
        spec.loader.exec_module(module)
    return module


class DispatchMapPacketTests(unittest.TestCase):
    def test_missing_env_and_argument_fail_closed(self):
        for name in ('standard_bundle_runner.py', 'reciprocal_bundle_runner.py'):
            with self.subTest(name=name), patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, 'C109749_MAP_PACKET'):
                    load_runner(name).reviewed_map_packet(None)

    def test_diagnostic_packet_rejected_before_native(self):
        scratch = Path('.runtime-work').resolve()
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            path = Path(temporary) / 'map.json'
            path.write_text(json.dumps({'diagnostic_fixture': True,
                                        'reviewed_original_map': True}) + '\n')
            for name in ('standard_bundle_runner.py', 'reciprocal_bundle_runner.py'):
                with self.subTest(name=name), patch.dict(os.environ, {'C109749_MAP_PACKET': str(path)}):
                    with self.assertRaisesRegex(ValueError, 'reviewed original Native map'):
                        load_runner(name).reviewed_map_packet(None)

    def test_reviewed_env_path_and_explicit_override(self):
        scratch = Path('.runtime-work').resolve()
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            reviewed = Path(temporary) / 'reviewed.json'
            diagnostic = Path(temporary) / 'diagnostic.json'
            reviewed.write_text(json.dumps({'reviewed_original_map': True,
                                            'diagnostic_fixture': False}) + '\n')
            diagnostic.write_text(json.dumps({'diagnostic_fixture': True}) + '\n')
            for name in ('standard_bundle_runner.py', 'reciprocal_bundle_runner.py'):
                with self.subTest(name=name), patch.dict(os.environ, {'C109749_MAP_PACKET': str(reviewed)}):
                    runner = load_runner(name)
                    self.assertEqual(runner.reviewed_map_packet(None)[0], str(reviewed))
                    with self.assertRaisesRegex(ValueError, 'reviewed original Native map'):
                        runner.reviewed_map_packet(str(diagnostic))


if __name__ == '__main__':
    unittest.main()
