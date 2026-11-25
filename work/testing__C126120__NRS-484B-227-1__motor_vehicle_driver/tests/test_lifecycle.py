import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('c126120_runner_lifecycle', ROOT / 'runner.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class LifecycleTests(unittest.TestCase):
    def test_capture_restores_before_seal_and_failed_capture_remains_unsealed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = ROOT / 'cases/source_verified_single_movement_uturn'
            for name in ('site-plan.json', 'diagnostic-site.json', 'diagnostic-authority.txt'):
                (root / name).write_bytes((source / name).read_bytes())
            plan = json.loads((root / 'site-plan.json').read_text())
            plan['source_review_status'] = 'reviewed_original_map_and_cameras'
            plan['authority_review_status'] = 'reviewed_original_public_authority_document'
            (root / 'site-plan.json').write_text(json.dumps(plan))
            events = []
            world = types.SimpleNamespace(
                get_settings=lambda: types.SimpleNamespace(synchronous_mode=False,
                                                          fixed_delta_seconds=None),
                apply_settings=lambda settings: events.append('settings'))
            client = types.SimpleNamespace(set_timeout=lambda timeout: None,
                                           get_world=lambda: world)
            carla = types.ModuleType('carla')
            carla.Client = lambda host, port: client
            exchange = types.ModuleType('worker_exchange')
            exchange.__path__ = []
            native = types.ModuleType('worker_exchange.native_output')
            native.seal_capture = lambda *a, **kw: events.append('seal')
            restore_module = types.ModuleType('worker_exchange.world_restore')
            restore_module.snapshot = lambda c: events.append('snapshot') or {'saved': True}
            restore_module.restore = lambda c, s: events.append('restore') or {'restored': True}
            modules = {'carla': carla, 'worker_exchange': exchange,
                       'worker_exchange.native_output': native,
                       'worker_exchange.world_restore': restore_module}
            for failing in (False, True):
                output = root / ('failed' if failing else 'complete')
                output.mkdir()
                (output / 'construction.json').write_text('{}\n')
                events.clear()
                argv = ['runner.py', '--site-plan', str(root / 'site-plan.json'),
                        '--config', str(root / 'absent.json'), '--output-dir', str(output)]
                def execute(*args):
                    events.append('run')
                    if failing:
                        raise ValueError('capture failed')
                    return {'overview': 0}
                with patch.dict(sys.modules, modules), patch.object(sys, 'argv', argv), \
                     patch.object(RUNNER, 'run', side_effect=execute):
                    if failing:
                        with self.assertRaisesRegex(ValueError, 'capture failed'):
                            RUNNER.main()
                    else:
                        RUNNER.main()
                self.assertEqual(events, ['snapshot', 'settings', 'run', 'restore'] +
                                 ([] if failing else ['seal']))
                if failing:
                    self.assertFalse(json.loads((output / 'native-run-status.json').read_text())
                                     ['capture_sealed'])


if __name__ == '__main__':
    unittest.main()
