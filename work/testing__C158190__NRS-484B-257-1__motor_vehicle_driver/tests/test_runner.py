import json
import queue
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import CAMERAS, camera_transforms, sensor_frame, validate_config


class RunnerTests(unittest.TestCase):
    def test_cpu_config_and_exact_case_selection(self):
        config = json.loads((ROOT / 'config.json').read_text())
        self.assertEqual(validate_config(config)['rate_hz'], 20)
        self.assertEqual(len(CAMERAS), 4)
        for case_id in config['supported_case_ids']:
            candidate = dict(config, selected_case_id=case_id)
            self.assertEqual(validate_config(candidate)['selected_case_id'], case_id)
        bad = dict(config, selected_case_id='unknown')
        with self.assertRaisesRegex(ValueError, 'Unknown exact'):
            validate_config(bad)
        bad = dict(config, cameras=config['cameras'][:-1])
        with self.assertRaisesRegex(ValueError, 'Four named'):
            validate_config(bad)

    def test_source_frame_join_discards_only_older_images(self):
        q = queue.Queue()
        q.put(type('Image', (), {'frame': 9})())
        q.put(type('Image', (), {'frame': 10})())
        self.assertEqual(sensor_frame(q, 10).frame, 10)
        q.put(type('Image', (), {'frame': 12})())
        with self.assertRaisesRegex(ValueError, 'skipped frame'):
            sensor_frame(q, 11)

    def test_all_camera_transforms_have_distinct_origins(self):
        class Carla:
            @staticmethod
            def Location(**kwargs): return kwargs
            @staticmethod
            def Rotation(**kwargs): return kwargs
            @staticmethod
            def Transform(location, rotation): return location, rotation
        transforms = camera_transforms(Carla)
        self.assertEqual(set(transforms), set(CAMERAS))
        origins = [tuple(transform[0].values()) for transform in transforms.values()]
        self.assertEqual(len(set(origins)), 4)
