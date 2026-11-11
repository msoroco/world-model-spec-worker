"""Two-approach stop-line feedback for the signal-off comparison.

The controller uses source-selected geometry and Native speed/body feedback.
Its engineering tolerances are control parameters, not statutory definitions.
"""
import math


def front_speed(actor):
    pose = actor.get_transform()
    vertices = actor.bounding_box.get_world_vertices(pose)
    if len(vertices) < 4:
        raise ValueError("Complete Native body required for stop approach")
    angle = math.radians(float(pose.rotation.yaw))
    ahead = (math.cos(angle), math.sin(angle))
    points = [(float(v.x), float(v.y)) for v in vertices]
    if any(not math.isfinite(v) for p in points for v in p):
        raise ValueError("Finite Native body required for stop approach")
    front = max(points, key=lambda p: p[0]*ahead[0] + p[1]*ahead[1])
    velocity = actor.get_velocity()
    components = [float(getattr(velocity, axis)) for axis in "xyz"]
    if any(not math.isfinite(v) for v in components):
        raise ValueError("Finite Native speed required for stop approach")
    return front, math.sqrt(sum(v*v for v in components)), ahead


def _distance_to_segment(point, segment):
    a, b = segment
    dx, dy = b[0]-a[0], b[1]-a[1]
    norm = dx*dx + dy*dy
    if norm <= 0:
        raise ValueError("Nondegenerate stop reference required")
    t = max(0, min(1, ((point[0]-a[0])*dx + (point[1]-a[1])*dy)/norm))
    return math.hypot(point[0]-a[0]-t*dx, point[1]-a[1]-t*dy)


class StopApproach:
    """Brake toward a reference, observe a full stop, then allow release."""

    def __init__(self, segment_xy_m, hold_frames=2, stop_tolerance_m=1.5):
        if (not isinstance(segment_xy_m, list) or len(segment_xy_m) != 2
                or any(not isinstance(p, list) or len(p) != 2
                       or any(type(v) not in (int, float) or not math.isfinite(v) for v in p)
                       for p in segment_xy_m)):
            raise ValueError("Finite source-selected stop segment required")
        _distance_to_segment(segment_xy_m[0], segment_xy_m)
        if type(hold_frames) is not int or hold_frames < 1 or not 0 < stop_tolerance_m <= 3:
            raise ValueError("Positive engineering stop controls required")
        self.segment = segment_xy_m
        self.hold_frames = hold_frames
        self.tolerance = stop_tolerance_m
        self.phase = "approach"
        self.stopped_frames = 0

    def step(self, front_xy_m, speed_mps, forward_xy, release_allowed):
        if (len(front_xy_m) != 2 or len(forward_xy) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       for v in (*front_xy_m, *forward_xy, speed_mps))
                or speed_mps < 0 or type(release_allowed) is not bool):
            raise ValueError("Finite measured front, speed and release required")
        center = [(self.segment[0][i] + self.segment[1][i])/2 for i in (0,1)]
        ahead_m = sum((center[i]-front_xy_m[i])*forward_xy[i] for i in (0,1))
        distance_m = _distance_to_segment(front_xy_m, self.segment)
        if self.phase == "approach":
            # An engineering braking estimate; actual stop position is measured.
            trigger_m = max(.8, speed_mps*speed_mps/(2*7.0) + .5)
            if ahead_m <= trigger_m:
                self.phase = "holding"
        if self.phase == "holding":
            if speed_mps == 0 and distance_m <= self.tolerance:
                self.stopped_frames += 1
            else:
                self.stopped_frames = 0
            if self.stopped_frames >= self.hold_frames and release_allowed:
                self.phase = "released"
        return {"hold": self.phase != "released" if self.phase != "approach" else False,
                "phase": self.phase, "front_distance_to_reference_m": distance_m,
                "reference_ahead_m": ahead_m,
                "recorded_zero_speed_frames_near_reference": self.stopped_frames,
                "engineering_tolerances_not_legal": True}
