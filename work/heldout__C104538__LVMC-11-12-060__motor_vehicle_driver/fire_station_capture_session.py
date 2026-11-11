"""Retain original subject body and mapped fire-station entrance observations."""
import json
from math import hypot, radians
from pathlib import Path


def _corners(actor):
    transform = actor.get_transform()
    box = actor.bounding_box
    # CARLA's bounding-box transform supplies the actual oriented corners.
    vertices = box.get_world_vertices(transform)
    return [[float(v.x), float(v.y)] for v in vertices]


class FireStationCaptureSession:
    def __init__(self, output, pipeline_capture, world_map, ego, geometry):
        from worker_exchange.native_output import FrameMap
        root = Path(output)
        for name in ('station_context.json', 'participant_state.jsonl', 'video_frames.jsonl'):
            if (root/name).exists():
                raise ValueError('retain prior original source: '+name)
        (root/'station_context.json').write_text(json.dumps(geometry, indent=2)+'\n')
        self.participants = (root/'participant_state.jsonl').open('x')
        self.frames = FrameMap(root/'video_frames.jsonl')
        self.pipeline = pipeline_capture
        self.world_map = world_map
        self.ego = ego
        self.closed = False

    def capture(self, frame, time_s):
        if self.closed or not self.ego.is_alive:
            raise ValueError('subject absent from original capture')
        original = self.pipeline.capture(frame, time_s)
        if (original.get('frame'), original.get('time_s')) != (frame, time_s):
            raise ValueError('original frame join differs')
        transform = self.ego.get_transform()
        p = transform.location
        waypoint = self.world_map.get_waypoint(p)
        if waypoint is None:
            raise ValueError('subject has no mapped waypoint')
        velocity = self.ego.get_velocity()
        self.participants.write(json.dumps({'frame': frame, 'time_s': time_s,
            'ego': {'actor_id': int(self.ego.id),
                'center_xy': [float(p.x), float(p.y)],
                'heading_rad': radians(float(transform.rotation.yaw)),
                'speed_mps': hypot(velocity.x, velocity.y),
                'lane_id': [int(waypoint.road_id), int(waypoint.lane_id)],
                'body_vertices_xy': _corners(self.ego)}})+'\n')
        self.participants.flush()
        self.frames.append(frame, time_s)
        return original

    def close(self):
        if not self.closed:
            self.closed = True
            self.frames.close()
            self.participants.close()
