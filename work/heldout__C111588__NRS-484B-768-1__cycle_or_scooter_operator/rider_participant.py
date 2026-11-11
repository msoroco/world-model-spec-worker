"""Original per-frame participant position and rider clearance capture."""
import json
from math import hypot
from pathlib import Path


def spawn(world, carla, library, route, offset_m):
    if offset_m not in (3.0, 8.0):
        raise ValueError('Unexpected controlled participant offset')
    transform = route[0].transform
    location = transform.location
    offset = carla.Location(x=location.x, y=location.y + offset_m, z=location.z)
    participant = world.try_spawn_actor(library.filter('walker.pedestrian.*')[0],
                                        carla.Transform(offset, transform.rotation))
    if participant is None:
        raise ValueError('Native participant spawn failed')
    participant.apply_control(carla.WalkerControl(
        direction=carla.Vector3D(x=0.0, y=-1.0, z=0.0), speed=1.0))
    return participant


class Recorder:
    def __init__(self, output):
        root = Path(output)
        self.motion = (root / 'participant_motion.jsonl').open('x')
        self.clearance = (root / 'clearance_samples.jsonl').open('x')

    def capture(self, frame, time_s, trace, participant, rider):
        location = participant.get_transform().location
        other = [float(location.x), float(location.y), float(location.z)]
        point = trace['position_m']
        distance = hypot(float(point[0])-other[0], float(point[1])-other[1])
        self.motion.write(json.dumps({'frame': frame, 'time_s': time_s,
            'actor_id': str(participant.id), 'position_m': other,
            'participant_half_width_m': abs(float(participant.bounding_box.extent.y)),
            'rider_half_width_m': abs(float(rider.bounding_box.extent.y))}) + '\n')
        self.clearance.write(json.dumps({'frame': frame, 'time_s': time_s,
            'participant_actor_id': str(participant.id),
            'center_distance_m': distance}) + '\n')

    def close(self):
        self.motion.close()
        self.clearance.close()
