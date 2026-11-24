"""Engineering placement controls for other-user contrast cases.

Original saved positions decide whether the requested exhibition region was
realized. Controller commands do not establish lawful use or right of way.
"""
from __future__ import annotations

import math

from dual_green import check_site, require


class OtherUserController:
    def __init__(self, case_id, site, source_root, carla, other):
        check_site(site, source_root)
        prefix = "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver__"
        require(case_id.startswith(prefix), "other-user controller case mismatch")
        suffix = case_id[len(prefix):]
        require(suffix in ("dual_vehicle_present", "dual_pedestrian_present",
                           "dual_pedestrian_late"), "other-user controller case mismatch")
        self.suffix = suffix
        self.site = site
        self.carla = carla
        self.other = other
        self.last_index = -1
        if suffix == "dual_pedestrian_late":
            target = site.get("other_user_target_xy")
            start = site.get("late_start_frame_index")
            require(isinstance(target, list) and len(target) == 2 and
                    all(math.isfinite(float(v)) for v in target),
                    "late pedestrian needs surveyed target")
            require(type(start) is int and 1 <= start < 900,
                    "late pedestrian needs positive delayed start")

    def __call__(self, other, index):
        require(other is self.other and index == self.last_index + 1,
                "other-user controller identity or tick order changed")
        self.last_index = index
        if self.suffix == "dual_vehicle_present":
            other.apply_control(self.carla.VehicleControl(
                throttle=0.0, brake=1.0, steer=0.0, hand_brake=True))
            return {"engineering_stationary_request": True, "legal_use_verdict": None}
        if self.suffix == "dual_pedestrian_present" or index < self.site["late_start_frame_index"]:
            other.apply_control(self.carla.WalkerControl(
                direction=self.carla.Vector3D(0.0, 0.0, 0.0), speed=0.0))
            return {"engineering_stationary_request": True, "legal_use_verdict": None}
        location = other.get_location()
        target = self.site["other_user_target_xy"]
        dx, dy = float(target[0]) - float(location.x), float(target[1]) - float(location.y)
        distance = math.hypot(dx, dy)
        speed = min(1.2, distance / 0.05) if distance > 0.1 else 0.0
        direction = self.carla.Vector3D(dx / distance if distance else 0.0,
                                         dy / distance if distance else 0.0, 0.0)
        other.apply_control(self.carla.WalkerControl(direction=direction, speed=speed))
        return {"engineering_stationary_request": speed == 0,
                "requested_speed_mps": speed, "legal_use_verdict": None}
