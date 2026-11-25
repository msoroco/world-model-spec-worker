import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from compare_saved import compare
from native_history_capture import CAMERAS, capture
from saved_finalizer import finalize
from test_native_history_capture import Actor, World


class ComparisonTest(unittest.TestCase):
    def setUp(self):
        scratch = PACKAGE.parents[1] / '.runtime-work' / 'c125763-comparison-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        world = World()
        for name in ('device', 'highway'):
            (self.root / (name + '.txt')).write_text(name + ' source\n')
        self.scene = {
            'map_sha256': hashlib.sha256(world.map.to_opendrive().encode()).hexdigest(),
            'reviewer': 'fixture reviewer', 'source_citation': 'diagnostic only',
            'cell_id': 'C125763', 'control': 'yield_sign',
            'ego_highway': 'A', 'other_highway': 'B',
            'approach_relation': 'crossing', 'ego_side': 'left',
            'intersection_bounds_xy_m': [0, -1, 2, 1],
            'ego_route': [[-5, 0, 0], [-1, 0, 0]],
            'other_route': [[0, -5, 0], [0, -1, 0]],
            'ego_lane': {'road_id': 1, 'lane_id': 1},
            'other_lane': {'road_id': 2, 'lane_id': 1},
            'ego_blueprint': 'vehicle.ego', 'other_blueprint': 'vehicle.other',
            'weather': {'cloudiness': 0},
            'camera_poses': {name: {'x': 0, 'y': 0, 'z': 2,
                                   'pitch': 0, 'yaw': 0, 'roll': 0} for name in CAMERAS},
            'camera_mounts': {name: 'ego' if name == 'driver_reference' else 'world'
                              for name in CAMERAS},
            'camera_dimensions': {name: [2, 2] for name in CAMERAS},
            'release_s': {'entry_below': 0, 'entry_inside': .5, 'entry_above': 1},
            'ego_release_s': 0,
        }
        for name in ('device', 'highway'):
            path = self.root / (name + '.txt')
            self.scene[name + '_source'] = {
                'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'citation': 'fixture only'}
        stream = io.BytesIO()
        Image.new('RGB', (2, 2)).save(stream, format='PNG')
        png = stream.getvalue()
        self.readers = {name: lambda frame, png=png: {'frame': frame, 'png_bytes': png}
                        for name in CAMERAS}

    def _spec(self, *, changed_weather=False):
        cases = []
        for probe in ('entry_below', 'entry_inside', 'entry_above'):
            world = World()
            packet = self.root / ('site-' + probe + '.json')
            scene = json.loads(json.dumps(self.scene))
            if changed_weather and probe == 'entry_inside':
                scene['weather']['cloudiness'] = 90
            packet.write_text(json.dumps(scene) + '\n')
            ego = Actor(world, 10, [-2, -1, 0, 1])
            other = Actor(world, 11, [-2, -2, -1, 0])
            attempt = self.root / ('capture-' + probe)
            capture(world, packet, ego, other, attempt, 4,
                    camera_readers=self.readers,
                    camera_dimensions=self.scene['camera_dimensions'])
            manifest_sha = hashlib.sha256((attempt / 'source-manifest.json').read_bytes()).hexdigest()
            result_path = self.root / ('result-' + probe + '.json')
            finalize(attempt, result_path, expected_manifest_sha256=manifest_sha,
                     probe_id=probe)
            cases.append({'case_id': 'testing__C125763__NRS-484B-250-2__motor_vehicle_driver__' + probe,
                          'attempt': str(attempt), 'source_manifest_sha256': manifest_sha,
                          'saved_result': str(result_path),
                          'saved_result_sha256': hashlib.sha256(result_path.read_bytes()).hexdigest()})
        spec = self.root / 'comparison-spec.json'
        spec.write_text(json.dumps({'comparison_id': 'entry_timing_range', 'cases': cases}) + '\n')
        return spec, cases

    def test_source_bound_three_case_comparison_and_fixed_condition_negative(self):
        spec, cases = self._spec()
        result = compare(PACKAGE / 'case-plan.json', spec)
        self.assertEqual([item['release_s'] for item in result['observed']], [0, .5, 1])
        self.assertFalse(result['legal_verdict_claimed'])

    def test_source_bound_changed_weather_is_not_isolated_timing(self):
        spec, cases = self._spec(changed_weather=True)
        with self.assertRaisesRegex(ValueError, 'fixed scene conditions differ'):
            compare(PACKAGE / 'case-plan.json', spec)

    def test_missing_camera_source_and_changed_saved_result_rejected(self):
        spec, cases = self._spec()
        result = Path(cases[0]['saved_result'])
        original = result.read_bytes()
        result.write_bytes(original + b' ')
        with self.assertRaisesRegex(ValueError, 'saved result bytes changed'):
            compare(PACKAGE / 'case-plan.json', spec)
        result.write_bytes(original)
        camera = Path(cases[2]['attempt']) / 'original-frames/overview-000001.png'
        camera.unlink()
        with self.assertRaisesRegex(ValueError, 'not a retained file'):
            compare(PACKAGE / 'case-plan.json', spec)


if __name__ == '__main__':
    unittest.main()
