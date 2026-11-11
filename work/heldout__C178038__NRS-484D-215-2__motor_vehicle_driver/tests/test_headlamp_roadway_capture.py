import json
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from headlamp_roadway_capture import RoadwaySourceRecorder


class RoadwayCaptureTests(unittest.TestCase):
    def test_raw_roadway_context_and_frame_join(self):
        with tempfile.TemporaryDirectory() as directory:
            waypoint = NS(road_id=4, lane_id=-1, lane_type='Shoulder')
            world = NS(get_map=lambda: NS(get_waypoint=lambda *args, **kwargs: waypoint),
                       get_weather=lambda: NS(sun_altitude_angle=-12.5))
            ego = NS(id=7, get_transform=lambda: NS(location=object()))
            carla = NS(LaneType=NS(Driving=1, Shoulder=2))
            recorder = RoadwaySourceRecorder(directory, world, ego, carla)
            row = recorder.append(10, .5)
            self.assertEqual((row['ego_id'], row['lane_type_readback']), ('7', 'Shoulder'))
            with self.assertRaisesRegex(ValueError, '20 Hz'):
                recorder.append(12, .55)
            recorder.append(11, .55)
            recorder.close()
            rows = [json.loads(line) for line in
                    (Path(directory) / 'roadway_environment.jsonl').read_text().splitlines()]
            self.assertEqual([r['frame'] for r in rows], [10, 11])
            with self.assertRaises(FileExistsError):
                RoadwaySourceRecorder(directory, world, ego, carla)


if __name__ == '__main__':
    unittest.main()
