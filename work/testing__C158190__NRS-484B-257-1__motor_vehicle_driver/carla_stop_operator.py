"""CARLA-lazy operator for the fixed C158190 stop-sign branch.

The source-reviewed site, Native map and sign readback must agree before any
recording is sealed. Controller hold durations are engineering interventions;
they are not legal definitions of an immediate hazard or proper yielding.
"""

from __future__ import annotations

import math
import json
from pathlib import Path

from carla_yield_operator import CarlaYieldOperator, _speed, validate_scene
from stop_sign_branch import CASES, SOURCES


class CarlaStopOperator(CarlaYieldOperator):
    def __init__(self, world, site, case_id, carla):
        if case_id not in CASES or site.get("control") != "stop_sign":
            raise ValueError("fixed stop-sign case identity required")
        sign = site.get("stop_sign", {})
        if not isinstance(sign.get("transform"), dict):
            raise ValueError("reviewed stop-sign transform required")
        # The shared sensor and body-readback methods need these internal
        # names. No yield sign is constructed or claimed by this adapter.
        adapted = dict(site)
        adapted["yield_sign"] = sign
        adapted["yield_sign_survey_sha256"] = site["stop_sign_survey_sha256"]
        super().__init__(world, adapted, case_id, carla)
        self.original_site = site
        config = json.loads((Path(__file__).resolve().parent / "config.json").read_text())
        self.brake_distance_multiplier = float(config.get("stop_brake_distance_multiplier", 1.0))
        if not 1.0 <= self.brake_distance_multiplier <= 2.0:
            raise ValueError("stop brake distance multiplier outside reviewed engineering range")
        self.stop_started_frame = None
        self.stop_released = False

    def read_control(self, approach):
        sign = self.original_site["stop_sign"]
        if approach != sign["governed_approach_id"]:
            raise ValueError("governed stop approach identity differs")
        self.map_bytes(self.world)
        transform = sign["transform"]
        for landmark in self.world.get_map().get_all_landmarks():
            kind = str(getattr(landmark, "type", "")).lower()
            if kind not in ("206", "stop", "205", "yield"):
                continue
            location = landmark.transform.location
            if math.hypot(location.x - transform["x"], location.y - transform["y"]) < 12:
                return "stop_sign" if kind in ("206", "stop") else "yield_sign"
        for actor in self.world.get_actors():
            kind = str(getattr(actor, "type_id", "")).lower()
            if "stop" not in kind and "yield" not in kind:
                continue
            location = actor.get_transform().location
            if math.hypot(location.x - transform["x"], location.y - transform["y"]) < 12:
                return "stop_sign" if "stop" in kind else "yield_sign"
        return None

    def release_through_vehicle(self, actor_id):
        self.destroy(actor_id)

    def control_frame(self, case_id, index):
        if case_id != self.case_id or self.ego is None or self.through is None:
            raise ValueError("Native stop controller ownership differs")
        plan = self.original_site["case_plans"][case_id]
        nearest = min((row["distance_to_intersection_m"], row["station_id"])
                      for row in self.original_site["approach_view_stations"]
                      if row["reviewed_visible"])[1]
        stations = [row for row in self.scene["approach_view_stations"]
                    if row.get("station_id") == nearest]
        if len(stations) != 1:
            raise ValueError("reviewed nearest-view controller anchor missing")
        anchor = stations[0]
        position = self.ego.get_transform().location
        near_anchor = math.hypot(position.x - anchor["x"], position.y - anchor["y"]) <= (self.scene["brake_distance_m"] * self.brake_distance_multiplier)
        speed = _speed(self.ego)
        if near_anchor and speed <= 0.15 and self.stop_started_frame is None:
            self.stop_started_frame = index
        if self.stop_started_frame is not None and index - self.stop_started_frame >= round(plan["stop_hold_s"] * 20):
            self.stop_released = True
        target = self.scene["slow_speed_mps"] if self.stop_released or not near_anchor else 0.0
        self.ego.apply_control(self.carla.VehicleControl(
            throttle=0.35 if speed < target - 0.3 else 0.0,
            brake=0.6 if speed > target + 0.3 else 0.0))
        through_target = (self.scene["through_speed_mps"]
                          if index / 20 >= plan["through_start_delay_s"] else 0.0)
        through_speed = _speed(self.through)
        self.through.apply_control(self.carla.VehicleControl(
            throttle=0.35 if through_speed < through_target - 0.3 else 0.0,
            brake=0.6 if through_speed > through_target + 0.3 else 0.0))

    def read_original_context(self, site, case_id):
        if site is not self.original_site:
            raise ValueError("original stop site owner differs")
        context = super().read_original_context(self.site, case_id)
        context.pop("yield_sign_survey_sha256", None)
        context.update({"cell_id": "C158190", "control": "stop_sign",
                        "stop_sign_survey_sha256": site["stop_sign_survey_sha256"],
                        "planned_response": CASES[case_id],
                        "ego_route_id": site["ego_route_id"]})
        return context

    def read_original_frame(self, case_id, index, native_frame):
        row = super().read_original_frame(case_id, index, native_frame)
        row.pop("yield_sign_survey_sha256", None)
        row.update({"control": "stop_sign",
                    "stop_sign_survey_sha256": self.original_site["stop_sign_survey_sha256"]})
        return row


def make_adapter(world, site, case_id):
    import carla
    validate_scene(site)
    return CarlaStopOperator(world, site, case_id, carla)
