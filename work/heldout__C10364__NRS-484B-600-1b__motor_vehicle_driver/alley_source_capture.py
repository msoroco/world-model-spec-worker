"""Retain original Native participant footprints for the C10364 alley case."""

import json
from math import atan2, isfinite
from pathlib import Path


def ground_corners(actor):
    vertices = list(actor.bounding_box.get_world_vertices(actor.get_transform()))
    if len(vertices) != 8:
        raise ValueError("Native participant needs eight bounding-box vertices")
    if any(not all(isfinite(float(getattr(vertex, axis))) for axis in ("x", "y", "z"))
           for vertex in vertices):
        raise ValueError("Nonfinite Native participant bounding box")
    lower = sorted(vertices, key=lambda vertex: float(vertex.z))[:4]
    points = [(float(vertex.x), float(vertex.y)) for vertex in lower]
    if len(set(points)) != 4:
        raise ValueError("Native participant ground corners are duplicated")
    cx = sum(x for x, _ in points) / 4
    cy = sum(y for _, y in points) / 4
    points.sort(key=lambda point: atan2(point[1] - cy, point[0] - cx))
    area = abs(sum(points[i][0] * points[(i + 1) % 4][1]
                   - points[(i + 1) % 4][0] * points[i][1]
                   for i in range(4))) / 2
    if area <= 1e-6:
        raise ValueError("Native participant ground footprint has no area")
    return [list(point) for point in points]


class AlleySourceRecorder:
    """Write synchronized, original tick source rows once during capture."""

    def __init__(self, directory, ego, pedestrian, property_actor):
        self.actors = (ego, pedestrian, property_actor)
        ids = [actor.id for actor in self.actors]
        if any(value is None for value in ids) or len(set(ids)) != 3:
            raise ValueError("Alley participants need three distinct Native IDs")
        self.path = Path(directory) / "participant_footprints.jsonl"
        self.output = self.path.open("x")
        try:
            self.motion = (Path(directory) / "ego_motion.jsonl").open("x")
        except BaseException:
            self.output.close()
            raise
        self.previous = None

    def append(self, frame, time_s):
        if (type(frame) is not int or type(time_s) not in (int, float)
                or not isfinite(time_s)
                or self.previous is not None and
                (frame != self.previous[0] + 1 or time_s <= self.previous[1])):
            raise ValueError("Missing or unordered Native alley frame")
        ego, pedestrian, prop = self.actors
        row = {"frame": frame, "time_s": time_s,
               "ego_id": ego.id, "pedestrian_id": pedestrian.id,
               "property_id": prop.id,
               "ego_corners": ground_corners(ego),
               "pedestrian_corners": ground_corners(pedestrian),
               "property_corners": ground_corners(prop)}
        velocity = ego.get_velocity()
        acceleration = ego.get_acceleration()
        forward = ego.get_transform().get_forward_vector()
        motion = {"frame": frame, "time_s": time_s,
                  "ego_id": ego.id,
                  "velocity_xy": [float(velocity.x), float(velocity.y)],
                  "acceleration_xy": [float(acceleration.x), float(acceleration.y)],
                  "forward_xy": [float(forward.x), float(forward.y)]}
        if any(not isfinite(value) for key in ("velocity_xy", "acceleration_xy", "forward_xy")
               for value in motion[key]):
            raise ValueError("Nonfinite Native ego motion readback")
        self.output.write(json.dumps(row, allow_nan=False) + "\n")
        self.motion.write(json.dumps(motion, allow_nan=False) + "\n")
        self.output.flush()
        self.motion.flush()
        self.previous = frame, time_s
        return row

    def close(self):
        self.output.close()
        self.motion.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
