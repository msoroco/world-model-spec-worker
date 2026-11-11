"""Record original Native body geometry and both headlamp bit readbacks."""

import json
from math import atan2, isfinite
from pathlib import Path


def _corners(actor):
    vertices = list(actor.bounding_box.get_world_vertices(actor.get_transform()))
    if len(vertices) != 8 or any(not all(isfinite(float(getattr(v, axis)))
                                      for axis in ('x', 'y', 'z')) for v in vertices):
        raise ValueError('Native following body vertices invalid')
    lower = sorted(vertices, key=lambda point: point.z)[:4]
    cx = sum(point.x for point in lower) / 4
    cy = sum(point.y for point in lower) / 4
    lower.sort(key=lambda point: atan2(point.y - cy, point.x - cx))
    return [[float(point.x), float(point.y)] for point in lower]


def _heading(actor):
    vector = actor.get_transform().get_forward_vector()
    if not all(isfinite(float(value)) for value in (vector.x, vector.y)):
        raise ValueError('Native following heading invalid')
    return [float(vector.x), float(vector.y)]


class HeadlampSourceRecorder:
    def __init__(self, output, ego, lead):
        if not ego.id or not lead.id or ego.id == lead.id:
            raise ValueError('Following vehicles need distinct Native identities')
        self.ego, self.lead = ego, lead
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        self.footprints = (output / 'following_footprints.jsonl').open('x')
        try:
            self.lamps = (output / 'headlamp_readbacks.jsonl').open('x')
        except BaseException:
            self.footprints.close()
            raise
        self.previous = None

    def append(self, frame, time_s, carla_module):
        if (type(frame) is not int or type(time_s) not in (int, float) or
                not isfinite(time_s) or
                self.previous and (frame != self.previous[0] + 1 or
                                   abs(time_s - self.previous[1] - .05) > 1e-4)):
            raise ValueError('Original following source is not joined at 20 Hz')
        state = self.ego.get_light_state()
        raw_state = int(state)
        high = bool(raw_state & int(carla_module.VehicleLightState.HighBeam))
        low = bool(raw_state & int(carla_module.VehicleLightState.LowBeam))
        footprint = {'frame': frame, 'time_s': time_s,
                     'ego_id': str(self.ego.id), 'lead_id': str(self.lead.id),
                     'ego_corners_xy': _corners(self.ego),
                     'lead_corners_xy': _corners(self.lead),
                     'ego_heading_xy': _heading(self.ego),
                     'lead_heading_xy': _heading(self.lead)}
        lamp = {'frame': frame, 'time_s': time_s,
                'uppermost_distribution': high, 'low_beam_readback': low,
                'native_light_state_int': raw_state}
        self.footprints.write(json.dumps(footprint, allow_nan=False) + '\n')
        self.lamps.write(json.dumps(lamp, allow_nan=False) + '\n')
        self.footprints.flush()
        self.lamps.flush()
        self.previous = frame, time_s
        return footprint, lamp

    def close(self):
        self.footprints.close()
        self.lamps.close()
