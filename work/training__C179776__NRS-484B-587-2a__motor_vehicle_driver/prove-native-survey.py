"""Exercise the Native survey calls with a fake CARLA map API."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('c179776_runner', ROOT / 'runner.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeCarla:
    LaneType = SimpleNamespace(Driving='driving', Shoulder='shoulder')

    @staticmethod
    def Location(x, y, z):
        return SimpleNamespace(x=x, y=y, z=z)


class FakeMap:
    def __init__(self, wrong=None):
        self.queries = []
        self.wrong = wrong

    def get_waypoint(self, location, project_to_road, lane_type):
        self.queries.append((location.x, location.y, lane_type, project_to_road))
        if not project_to_road:
            raise AssertionError('Survey did not project to native road')
        lane_id = 2 if location.y == 5 else (1 if location.y == 2 else -1)
        if self.wrong == 'missing_shoulder' and lane_id == 2:
            return None
        if self.wrong == 'wrong_lane' and lane_id == 2:
            lane_id = 1
        center = location.y + (.6 if self.wrong == 'lateral_shift' else 0)
        return SimpleNamespace(road_id=1, lane_id=lane_id, lane_type=lane_type,
                               lane_width=2 if lane_id == 2 else 4,
                               transform=SimpleNamespace(location=SimpleNamespace(y=center)))


class FakeWorld:
    def __init__(self, wrong=None):
        self.map = FakeMap(wrong)

    def get_map(self):
        return self.map


world = FakeWorld()
rows = module.survey(world, FakeCarla)
assert len(rows) == 9 and len(world.map.queries) == 9
assert {row['lane_id'] for row in rows} == {-1, 1, 2}
assert all(row['road_id'] == 1 for row in rows)
errors = {}
for wrong in ('missing_shoulder', 'wrong_lane', 'lateral_shift'):
    try:
        module.survey(FakeWorld(wrong), FakeCarla)
    except RuntimeError as error:
        errors[wrong] = str(error)
    else:
        raise AssertionError('Invalid Native readback accepted: ' + wrong)
print(json.dumps({'passed': True, 'surveyed_waypoints': 9,
                  'rejected_readbacks': errors,
                  'original_native_execution_claimed': False}, sort_keys=True))
