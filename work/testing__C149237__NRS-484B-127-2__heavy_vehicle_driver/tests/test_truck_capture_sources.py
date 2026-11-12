import importlib.util
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


spec = importlib.util.spec_from_file_location('truck_capture_sources', Path(__file__).resolve().parents[1] / 'truck_capture_sources.py')
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)


class FakeActor:
    def __init__(self, ident, x, width=2.2, blueprint='vehicle.carlamotors.european_hgv'):
        self.id, self.x, self.type_id = ident, x, blueprint
        points = [NS(x=x+dx, y=dy) for dx, dy in
                  ((-5,-width/2),(-5,width/2),(5,width/2),(5,-width/2))]
        self.bounding_box = NS(extent=NS(y=width/2),
                               get_world_vertices=lambda transform: points)

    def get_transform(self):
        return NS(location=NS(x=self.x,y=-1.9))

    def get_velocity(self):
        return NS(x=12.0,y=0.0,z=0.0)


class FrameMap:
    def append(self, frame, time):
        return {'video_frame': 0, 'carla_frame': frame, 'time_s': time}


class CaptureSourceTests(unittest.TestCase):
    def test_retains_original_ids_bodies_widths_and_frame(self):
        history = io.StringIO()
        snap = NS(frame=43, timestamp=NS(elapsed_seconds=2.15))
        waypoint = NS(road_id=149237,lane_id=-1)
        mapping = sources.record_sample(FrameMap(),history,snap,
                                        FakeActor(1,100),FakeActor(2,260),waypoint,waypoint)
        row = json.loads(history.getvalue())
        self.assertEqual(mapping,{'video_frame':0,'frame':43})
        self.assertEqual((row['frame'],row['time_s']),(43,2.15))
        self.assertEqual((row['ego']['actor_id'],row['lead']['actor_id']),(1,2))
        self.assertEqual(row['ego']['overall_width_m'],2.2)
        self.assertEqual(len(row['lead']['body_vertices_xy_m']),4)

    def test_rejects_missing_lane_and_nonfinite_body(self):
        snap = NS(frame=43,timestamp=NS(elapsed_seconds=2.15))
        waypoint = NS(road_id=149237,lane_id=-1)
        with self.assertRaisesRegex(ValueError,'lane readback'):
            sources.record_sample(FrameMap(),io.StringIO(),snap,FakeActor(1,100),
                                  FakeActor(2,260),waypoint,None)
        bad = FakeActor(2,float('nan'))
        with self.assertRaisesRegex(ValueError,'Nonfinite Native truck body'):
            sources.record_sample(FrameMap(),io.StringIO(),snap,FakeActor(1,100),
                                  bad,waypoint,waypoint)


if __name__ == '__main__':
    unittest.main()
