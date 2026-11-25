import importlib.util
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('c126120_capture', ROOT / 'native_capture.py')
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)


class NativeCaptureTests(unittest.TestCase):
    def test_original_gear_and_four_camera_frame_join(self):
        plan = json.loads((ROOT / 'cases/source_verified_multiple_movement_uturn/route-plan.json').read_text())
        movement, frames = io.StringIO(), io.StringIO()
        images = {name: NS(frame=101, width=size[0], height=size[1])
                  for name, size in CAPTURE.CAMERAS.items()}
        written = {name: [] for name in CAPTURE.CAMERAS}
        recorder = CAPTURE.OriginalTickRecorder(plan['divider_context'], movement, frames,
            {name: target.append for name, target in written.items()})
        vertices = [NS(x=x, y=y) for x, y in ((4,-6),(4,-4),(6,-4),(6,-6))]
        def actor(identifier, reverse):
            return NS(id=identifier,
                      bounding_box=NS(get_world_vertices=lambda transform: vertices),
                      get_transform=lambda: NS(rotation=NS(yaw=90)),
                      get_control=lambda: NS(reverse=reverse))
        snapshot = NS(frame=101, timestamp=NS(elapsed_seconds=5.05))
        recorder.record(snapshot, actor(1, True), actor(2, False), images, road_id=7)
        row = json.loads(movement.getvalue())
        self.assertEqual(row['ego_gear'], 'reverse')
        self.assertEqual(json.loads(frames.getvalue())['carla_frame'], 101)
        self.assertTrue(all(len(items) == 1 for items in written.values()))
        with self.assertRaisesRegex(ValueError, 'Nonmonotone'):
            recorder.record(snapshot, actor(1, True), actor(2, False), images, road_id=7)


if __name__ == '__main__':
    unittest.main()
