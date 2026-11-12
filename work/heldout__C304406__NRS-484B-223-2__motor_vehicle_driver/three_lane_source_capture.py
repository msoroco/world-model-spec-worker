"""Retain map lane geometry and original ego body at 20 Hz."""

import json
from pathlib import Path

from three_lane_route import ordered_lanes, section_readback, _unit, _xy
from three_lane_measurement import CONDITIONS


def lane_polygon(waypoint, length_m=12):
    tangent = _unit(waypoint)
    left = (-tangent[1], tangent[0])
    center = _xy(waypoint)
    half_width = float(waypoint.lane_width) / 2
    half_length = length_m / 2
    return [[center[0] + a * half_length * tangent[0] + b * half_width * left[0],
             center[1] + a * half_length * tangent[1] + b * half_width * left[1]]
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def original_row(frame, time_s, right_lane, ego):
    lanes = ordered_lanes(right_lane)
    vertices = ego.bounding_box.get_world_vertices(ego.get_transform())
    if len(vertices) < 4:
        raise ValueError('Original ego body vertices missing')
    return {'frame': frame, 'time_s': time_s, 'road_id': right_lane.road_id,
            'road_travel_tangent_xy': list(_unit(right_lane)),
            'ego_actor_id': str(ego.id),
            'ego_corners_xy': [[float(vertex.x), float(vertex.y)] for vertex in vertices[:4]],
            'lane_polygons_xy': {name: lane_polygon(waypoint)
                                 for name, waypoint in lanes.items()}}


class ThreeLaneSourceRecorder:
    def __init__(self, root, right_lane, ego):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.frames = self.root / 'three_lane_frames.jsonl'
        self.context = self.root / 'three_lane_context.json'
        self.map = self.root / 'three_lane_map_readback.json'
        for path in (self.frames, self.context, self.map):
            if path.exists():
                raise FileExistsError('Original source already exists: ' + path.name)
        self.right_lane = right_lane
        self.ego = ego
        readback = section_readback(right_lane)
        self.map.write_text(json.dumps(readback, allow_nan=False) + '\n')
        context = {name: {'value': None, 'source_ref': None} for name in CONDITIONS}
        context['map_marked_three_lane_candidate'] = {
            'value': True, 'source_ref': 'three_lane_map_readback.json'}
        self.context.write_text(json.dumps(context, allow_nan=False) + '\n')
        self.previous = None

    def append(self, frame, time_s, right_lane=None):
        if self.previous is not None and (frame != self.previous[0] + 1 or
                                          abs(time_s - self.previous[1] - 0.05) > 1e-4):
            raise ValueError('Original three-lane capture is not 20 Hz contiguous')
        selected = right_lane or self.right_lane
        if (selected.road_id, selected.lane_id) != (self.right_lane.road_id,
                                                    self.right_lane.lane_id):
            raise ValueError('Original three-lane road or right lane identity changed')
        row = original_row(frame, time_s, selected, self.ego)
        with self.frames.open('a') as output:
            output.write(json.dumps(row, allow_nan=False) + '\n')
        self.previous = frame, time_s
        return row
