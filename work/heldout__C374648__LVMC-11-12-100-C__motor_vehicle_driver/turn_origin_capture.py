"""Retain original Native lane, heading and map-marking rows at each tick.

Road markings here are map references, not spawned actors or proof of legal
designation. The authored center-lane role is retained separately for review.
"""

import json
from math import isfinite
from pathlib import Path


def _marking_ref(wp, side):
    marking = getattr(wp, side + '_lane_marking', None)
    if marking is None or str(marking.type).rsplit('.', 1)[-1].lower() == 'none':
        raise ValueError('Selected center lane lacks original map marking')
    kind = str(marking.type).rsplit('.', 1)[-1]
    color = str(getattr(marking, 'color', 'unknown')).rsplit('.', 1)[-1]
    return f'road:{int(wp.road_id)}:lane:{int(wp.lane_id)}:{side}:{kind}:{color}'


class TurnOriginRecorder:
    def __init__(self, output, carla_map, selection):
        path = Path(output) / 'turn_origin_native.jsonl'
        if path.exists():
            raise ValueError('Retain prior original turn-origin source')
        center = selection['center_approach'][0]
        self.markings = [_marking_ref(center, 'left'), _marking_ref(center, 'right')]
        self.center_road = selection['center_road_id']
        self.center_lane = selection['center_lane_id']
        self.map = carla_map
        self.file = path.open('w', encoding='utf-8')
        self.count = 0

    def append(self, ego, frame, time_s):
        wp = self.map.get_waypoint(ego.get_location(), project_to_road=True)
        if wp is None:
            raise ValueError('Original ego has no Native road waypoint')
        forward = ego.get_transform().get_forward_vector()
        if not all(isfinite(float(x)) for x in (time_s, forward.x, forward.y)):
            raise ValueError('Nonfinite original turn-origin row')
        row = {'frame': int(frame), 'time_s': float(time_s), 'ego_id': str(ego.id),
               'ego_forward_xy': [float(forward.x), float(forward.y)],
               'is_junction': bool(wp.is_junction), 'road_id': int(wp.road_id),
               'lane_id': int(wp.lane_id),
               'center_turn_road_id': int(self.center_road),
               'center_turn_lane_id': int(self.center_lane),
               'designation_source': 'authored center-lane candidate plus original map markings; authority undecided',
               'center_marking_source_ids': self.markings}
        self.file.write(json.dumps(row, allow_nan=False) + '\n')
        self.count += 1
        return row

    def close(self):
        self.file.close()
