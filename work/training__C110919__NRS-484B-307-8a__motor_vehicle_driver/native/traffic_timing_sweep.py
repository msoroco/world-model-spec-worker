"""Physical cross-traffic launch control and saved-source timing measurement.

The launch frame is an authored control. Conflict timing is measured only from
retained Native body and signal rows; it is never inferred from that command.
"""
from dataclasses import dataclass
import math

ZONE = (8.0, 12.0, -4.0, 4.0)


@dataclass(frozen=True)
class TrafficLaunch:
    start_frame: int
    stop_frame: int = 260
    total_frames: int = 480
    throttle: float = .25

    def __post_init__(self):
        if (type(self.start_frame) is not int or type(self.stop_frame) is not int or
                type(self.total_frames) is not int or
                not (0 <= self.start_frame < self.stop_frame < self.total_frames)):
            raise ValueError("Traffic launch frames must fit the exact capture")
        if not isinstance(self.throttle, (int, float)) or not math.isfinite(self.throttle) or not 0 < self.throttle <= 1:
            raise ValueError("Traffic throttle must be finite and positive")

    def command(self, frame):
        if type(frame) is not int or not 0 <= frame < self.total_frames:
            raise ValueError("Frame outside exact capture")
        moving = self.start_frame <= frame <= self.stop_frame
        return {"throttle": self.throttle if moving else 0.0,
                "steer": 0.0, "brake": 0.0 if moving else 1.0,
                "hand_brake": frame > self.stop_frame}


def intersects(body, zone=ZONE):
    if not isinstance(body, list) or len(body) != 4 or any(
            not isinstance(point, list) or len(point) != 2 or
            any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in point)
            for point in body):
        raise ValueError("Native horizontal body footprint missing")
    low_x, high_x, low_y, high_y = zone
    return (max(p[0] for p in body) >= low_x and min(p[0] for p in body) <= high_x and
            max(p[1] for p in body) >= low_y and min(p[1] for p in body) <= high_y)


def measure(samples, *, launch_frame, rate_hz=20):
    """Report observed Native conflict timing without a right-of-way verdict."""
    if len(samples) != 480 or rate_hz != 20:
        raise ValueError("Exact 480-frame, 20-Hz source required")
    TrafficLaunch(launch_frame)
    traffic_frames = []
    ego_frames = []
    overlap = []
    for index, row in enumerate(samples):
        if (row.get("synthetic_diagnostic") is True and
                row.get("speed_provenance") != "synthetic_native_sample"):
            raise ValueError("Diagnostic velocity provenance changed")
        if row.get("signal_state_observed") not in ("Red", "TrafficLightState.Red") or \
                row.get("other_traffic_signal_state_observed") not in ("Green", "TrafficLightState.Green"):
            raise ValueError("Directed signal source differs")
        if abs(row["time_s"] - (index + 1) / rate_hz) > .051:
            raise ValueError("Native frame/time sequence differs")
        traffic = intersects(row["other_traffic_body_xy_m"])
        ego = intersects(row["native_body_xy_m"])
        if row.get("traffic_conflict_occupied") is not traffic:
            raise ValueError("Stored traffic occupancy differs from Native body")
        if traffic:
            traffic_frames.append(index)
        if ego:
            ego_frames.append(index)
        if traffic and ego:
            overlap.append(index)
    if not traffic_frames or not ego_frames:
        raise ValueError("Observed traffic or ego conflict entry absent")
    first_traffic, first_ego = traffic_frames[0], ego_frames[0]
    return {"authored_launch_frame": launch_frame,
            "observed_traffic_first_frame": first_traffic,
            "observed_traffic_last_frame": traffic_frames[-1],
            "observed_ego_first_frame": first_ego,
            "ego_minus_traffic_entry_s": round((first_ego - first_traffic) / rate_hz, 3),
            "observed_overlap_frames": overlap,
            "measurement_source": "saved_native_bodies_and_signal_rows",
            "legal_right_of_way_verdict": None}
