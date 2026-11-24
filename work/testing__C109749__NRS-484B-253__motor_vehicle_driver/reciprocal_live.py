"""Three-vehicle live path for the two reciprocal C109749 cases.

CARLA is supplied by the caller. Original actor bodies, controls, camera pixels
and frame IDs are sealed by reciprocal_native_capture, not inferred from plans.
"""
from __future__ import annotations

import json
from pathlib import Path

from bundle_runner import check
from carla_live_adapter import CarlaTickAdapter, WorldLease, _heading, _vertices
from carla_scene_factory import RouteControls, _camera, _spawn_vehicle
from native_acquisition import CAMERAS
from native_source_review import review
from reciprocal_native_capture import capture_reciprocal


class ReciprocalControls(RouteControls):
    def __init__(self, api, request, packet, later):
        super().__init__(api, request, packet)
        self.later = later
        self.later_route = [(float(p["x_m"]), float(p["y_m"]))
                            for p in request["later_opposing_route"]]
        self.later_index = 1
        self.later_wait = request["controller"]["wait_for_later_opponent"]
        if type(self.later_wait) is not bool:
            raise ValueError("exact reciprocal response missing")

    def __call__(self, ego, opponent):
        super().__call__(ego, opponent)
        initial_clear = not self._inside(opponent, self.polygon)
        ego_committed = self._inside(ego, self.polygon)
        demand = self.target_speed if initial_clear and not (self.later_wait and ego_committed) else 0.0
        self.later_index, _ = self._drive(self.later, self.later_route,
                                         self.later_index, demand)


class ReciprocalTickAdapter:
    def __init__(self, base: CarlaTickAdapter, later):
        if later.id in (base.ego.id, base.opponent.id):
            raise ValueError("later Native vehicle identity aliases primary actor")
        self.base = base
        self.later = later
        self.attestation = base.attestation

    def source_attestation(self):
        return self.base.source_attestation()

    def tick(self):
        frame, time_s, primary, cameras = self.base.tick()
        control = self.later.get_control()
        speed = float(self.later.get_velocity().length())
        later = {"later_opponent_actor_id": self.later.id,
                 "later_opponent_vertices": _vertices(self.later),
                 "later_opponent_heading": _heading(self.later),
                 "later_opponent_speed_mps": speed,
                 "later_opponent_braking": float(control.brake) > 0,
                 "later_opponent_driver_control_source": "original Native get_control"}
        return frame, time_s, primary, cameras, later


def make_scene_factory(api):
    def scene_factory(*, world, request, packet, lease):
        review(packet, carla_map=world.get_map(),
               location_factory=lambda x, y: api.Location(x=x, y=y))
        if request["controller"]["wait_for_later_opponent"] is None or not request["later_opposing_route"]:
            raise ValueError("exact reciprocal later-actor route required")
        ego = _spawn_vehicle(world, api, lease, request["ego_blueprint_id"],
                             request["ego_spawn_waypoint"])
        opponent = _spawn_vehicle(world, api, lease, request["opponent_blueprint_id"],
                                  request["initial_opponent_spawn_waypoint"])
        later = _spawn_vehicle(world, api, lease, request["opponent_blueprint_id"],
                               request["later_opposing_route"][0])
        if len({ego.id, opponent.id, later.id}) != 3:
            raise ValueError("three distinct live vehicle identities required")
        if request["controller"]["signal_left"]:
            ego.set_light_state(api.VehicleLightState(int(api.VehicleLightState.LeftBlinker)))
        dimensions = [request["capture"]["overview_resolution"],
                      *request["capture"]["detail_resolutions"]]
        cameras = {name: _camera(world, api, lease, ego, name, *size)
                   for name, size in zip(CAMERAS, dimensions)}
        return {"ego": ego, "opponent": opponent, "later": later,
                "cameras": cameras,
                "control_step": ReciprocalControls(api, request, packet, later)}
    return scene_factory


def run(*, client, config_path, map_path, output, scene_factory,
        location_factory, left_blinker_mask, frame_count=900):
    config = json.loads(Path(config_path).read_text())
    packet = json.loads(Path(map_path).read_text())
    if packet.get("diagnostic_fixture") or packet.get("reviewed_original_map") is not True:
        raise ValueError("reciprocal Native capture needs reviewed map")
    request = check(config, packet)
    if request["case_id"].rsplit("__", 1)[-1] not in ("reciprocal_yield", "reciprocal_no_yield"):
        raise ValueError("exact reciprocal case required")
    if frame_count != request["capture"]["frame_count"]:
        raise ValueError("exact reciprocal 900-frame contract required")
    world = client.get_world()
    with WorldLease(world) as lease:
        scene = scene_factory(world=world, request=request, packet=packet, lease=lease)
        if set(scene) != {"ego", "opponent", "later", "cameras", "control_step"}:
            raise ValueError("three-actor scene incomplete")
        actors = [scene["ego"], scene["opponent"], scene["later"], *scene["cameras"].values()]
        if (len({id(actor) for actor in actors}) != 7 or
                any(actor not in lease.owned for actor in actors) or
                set(scene["cameras"]) != set(CAMERAS)):
            raise ValueError("unowned or aliased reciprocal Native actor")
        base = CarlaTickAdapter(world=world, packet=packet, ego=scene["ego"],
                                opponent=scene["opponent"], cameras=scene["cameras"],
                                control_step=scene["control_step"],
                                location_factory=location_factory,
                                left_blinker_mask=left_blinker_mask)
        adapter = ReciprocalTickAdapter(base, scene["later"])
        files = capture_reciprocal(adapter=adapter, case_id=request["case_id"],
                                   map_path=map_path, output=output, frame_count=frame_count)
        return {"case_id": request["case_id"], "files": files,
                "native_map_sha256": adapter.attestation["native_map_sha256"],
                "physical_acceptance": "unverified"}
