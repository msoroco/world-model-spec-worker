"""Capture raw roadway and sun-angle context for each following frame.

The sun angle does not determine the NRS 484D.100 civil-time premise. A waypoint
lane type is map context, not proof of actual tire occupancy or legal coverage.
"""

import json
from math import isfinite
from pathlib import Path


class RoadwaySourceRecorder:
    def __init__(self, output, world, ego, carla_module):
        self.world, self.ego, self.carla = world, ego, carla_module
        self.path = Path(output) / 'roadway_environment.jsonl'
        self.stream = self.path.open('x')
        self.previous = None

    def append(self, frame, time_s):
        if (type(frame) is not int or type(time_s) not in (int, float) or
                not isfinite(time_s) or
                self.previous is not None and
                (frame != self.previous[0] + 1 or
                 abs(time_s - self.previous[1] - .05) > 1e-4)):
            raise ValueError('Roadway context is not joined at 20 Hz')
        location = self.ego.get_transform().location
        lane_types = self.carla.LaneType.Driving | self.carla.LaneType.Shoulder
        waypoint = self.world.get_map().get_waypoint(
            location, project_to_road=False, lane_type=lane_types)
        weather = self.world.get_weather()
        sun = float(weather.sun_altitude_angle)
        if not isfinite(sun):
            raise ValueError('Native sun altitude is not finite')
        row = {'frame': frame, 'time_s': time_s,
               'ego_id': str(self.ego.id),
               'sun_altitude_angle_deg': sun,
               'road_id': waypoint.road_id if waypoint else None,
               'lane_id': waypoint.lane_id if waypoint else None,
               'lane_type_readback': str(waypoint.lane_type) if waypoint else None,
               'waypoint_present': waypoint is not None}
        self.stream.write(json.dumps(row, allow_nan=False) + '\n')
        self.stream.flush()
        self.previous = frame, time_s
        return row

    def close(self):
        self.stream.close()
