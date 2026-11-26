"""CPU proof that exceptional Native branches preserve per-frame source facts."""

from dataclasses import dataclass

from native_capture import original_control_state, original_viewpoint_rays
from stop_yield_scene import request


@dataclass
class Point:
    x: float
    y: float
    z: float


@dataclass
class Rotation:
    yaw: float


@dataclass
class Pose:
    location: Point
    rotation: Rotation


class Carla:
    Location = Point


class Hit:
    location = Point(-1, -4, 1)
    label = "Buildings"


class World:
    def cast_ray(self, start, end):
        assert start.z == end.z == 1.5
        return [Hit()]


class Actor:
    id = 17
    is_alive = True

    def get_transform(self):
        return Pose(Point(-3, -5, .5), Rotation(0))


class Signal(Actor):
    id = 19

    def get_state(self):
        return "Green"


class NoRays:
    pass


def rejects(operation, fragment):
    try:
        operation()
    except ValueError as error:
        assert fragment in str(error), str(error)
    else:
        raise AssertionError("Missing original source was accepted")


def main():
    rays = original_viewpoint_rays(World(), Carla(), 71, 3.5)
    assert rays["native_frame"] == 71 and len(rays["rays"]) == 18
    assert rays["nearest_legal_viewpoint_unassessed"] is True
    rejects(lambda: original_viewpoint_rays(NoRays(), Carla(), 71, 3.5), "cast_ray")
    police = original_control_state({"officer": Actor(), "signal": None},
                                    request("police_directed_control"), 71, 3.5)
    assert police["officer"]["actor_id"] == 17 and police["officer_direction_legally_unassessed"]
    rejects(lambda: original_control_state({"officer": None}, request("police_directed_control"), 71, 3.5),
            "officer actor unavailable")
    signal = original_control_state({"officer": None, "signal": Signal()},
                                    request("signal_directed_control"), 71, 3.5)
    assert signal["signal"]["state"] == "Green" and signal["signal_controls_approach_legally_unassessed"]
    rejects(lambda: original_control_state({"signal": None}, request("signal_directed_control"), 71, 3.5),
            "signal actor/state unavailable")
    print("Original viewpoint, officer, and signal readback paths pass; missing-source negatives reject")


if __name__ == "__main__":
    main()
