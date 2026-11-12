"""Original-tick body and physical-curb source writer for C152976."""
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path


def read_curb_source(path, surveyed_map_hash):
    path = Path(path)
    source = path.read_bytes()
    site = json.loads(source)
    if site.get('opendrive_sha256') != surveyed_map_hash:
        raise ValueError('Curbs differ from surveyed Native map')
    for field in ('source_id', 'curb_source', 'one_way_source',
                  'approach_left_curb_x', 'departure_left_curb_y'):
        if site.get(field) is None or site[field] == '':
            raise ValueError('Original curb/one-way source missing: '+field)
    for field in ('approach_left_curb_x', 'departure_left_curb_y'):
        if type(site[field]) not in (int, float) or not isfinite(site[field]):
            raise ValueError('Original curb coordinate invalid')
    site['site_file_sha256'] = sha256(source).hexdigest()
    return site


class OneWayNativeCapture:
    def __init__(self, output, ego, world_map, surveyed, curb_source):
        from worker_exchange.native_output import FrameMap
        self.ego = ego
        self.map = world_map
        self.surveyed = surveyed
        self.site = read_curb_source(curb_source, surveyed['opendrive_sha256'])
        self.root = Path(output)
        (self.root/'native').mkdir(exist_ok=True)
        self.frames = FrameMap(self.root/'video_frames.jsonl')
        self.bodies = (self.root/'native/footprints.jsonl').open('x')
        self.edges = (self.root/'native/road_edges.jsonl').open('x')
        self.previous = None

    def append(self, frame, time_s):
        if not self.ego.is_alive:
            raise ValueError('Original turning actor disappeared')
        if self.previous is not None and (frame != self.previous[0]+1 or time_s <= self.previous[1]):
            raise ValueError('Original turn frame identity missing or unordered')
        transform = self.ego.get_transform()
        wp = self.map.get_waypoint(transform.location)
        if wp is None:
            raise ValueError('Original turning actor left mapped road')
        points = self.ego.bounding_box.get_world_vertices(transform)
        corners = [[float(p.x), float(p.y)] for p in points]
        if len(corners) < 4 or any(not all(isfinite(v) for v in p) for p in corners):
            raise ValueError('Original full-body footprint missing')
        yaw = float(transform.rotation.yaw) % 360
        # The transition is classified from actual heading, not the intended case.
        north_error = abs(((yaw-90+180)%360)-180)
        west_error = abs(((yaw-180+180)%360)-180)
        if min(north_error, west_error) > 45:
            raise ValueError('Original turn heading left north-to-west route')
        direction = 'north' if north_error <= west_error else 'west'
        row = {'video_frame': self.frames.index, 'carla_frame': frame,
               'native_frame': frame, 'actor_id': self.ego.id,
               'road_id': int(wp.road_id), 'time_s': time_s,
               'body_corners_xy': corners}
        edge = {'video_frame': self.frames.index, 'carla_frame': frame,
                'native_frame': frame, 'road_id': int(wp.road_id),
                'time_s': time_s, 'native_road_direction': direction,
                'one_way_source': self.site['one_way_source'],
                'curb_source': self.site['curb_source'],
                'site_file_sha256': self.site['site_file_sha256'],
                'observed_left_curb_x': self.site['approach_left_curb_x'],
                'observed_left_curb_y': self.site['departure_left_curb_y']}
        self.bodies.write(json.dumps(row, allow_nan=False)+'\n'); self.bodies.flush()
        self.edges.write(json.dumps(edge, allow_nan=False)+'\n'); self.edges.flush()
        self.frames.append(frame, time_s, subject_actor_id=self.ego.id)
        self.previous = frame, time_s
        return row, edge

    def close(self):
        self.frames.close(); self.bodies.close(); self.edges.close()
