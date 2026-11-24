"""Two-vehicle Native entrypoint binds the reviewed scene and rejects bad inputs."""
import json
from pathlib import Path
import sys
import tempfile
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from native_entrypoint import run_native
from test_carla_scene_factory import API, World, packet


class NativeEntrypointTests(TestCase):
    def setUp(self):
        scratch = REPO / '.runtime-work/c109749-native-entrypoint-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = json.loads(next(f['content'] for f in json.loads(
            (ROOT / 'cases/inside_yield/construction.json').read_text())['files']
            if f['path'] == 'config.json'))
        self.packet = packet(World())
        self.config_path = self.root / 'config.json'
        self.map_path = self.root / 'map.json'
        self.output = self.root / 'attempt'

    def invoke(self):
        self.config_path.write_text(json.dumps(self.config))
        self.map_path.write_text(json.dumps(self.packet))
        return run_native(self.config_path, self.map_path, self.output,
                          api=API, client=object())

    def test_binds_two_vehicle_live_path(self):
        with mock.patch('live_capture.run', return_value={'physical_acceptance':'unverified'}) as runner:
            result = self.invoke()
        self.assertEqual(result['physical_acceptance'], 'unverified')
        self.assertEqual(runner.call_args.kwargs['output'], self.output)
        self.assertTrue(callable(runner.call_args.kwargs['scene_factory']))

    def test_rejects_diagnostic_and_reciprocal_before_capture(self):
        self.packet['diagnostic_fixture'] = True
        with self.assertRaisesRegex(ValueError, 'reviewed original'):
            self.invoke()
        self.packet.pop('diagnostic_fixture')
        self.config['selected_case_id'] = self.config['selected_case_id'].replace(
            'inside_yield', 'reciprocal_yield')
        self.config['controller']['wait_for_later_opponent'] = True
        self.packet['later_opposing_route'] = list(self.packet['opposing_route'])
        with self.assertRaisesRegex(ValueError, 'two-vehicle entrypoint'):
            self.invoke()

    def test_rejects_nonempty_attempt(self):
        self.output.mkdir()
        (self.output / 'prior.txt').write_text('prior\n')
        with self.assertRaisesRegex(ValueError, 'must be empty'):
            self.invoke()
