"""Native entrypoint for the C102304 traveling 500 ft construction draft.

The operator supplies an already owned CARLA endpoint.  This runner never
loads a new world or asserts a realized statutory distance.  Saved processing
measures the original body footprints after Native exit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from math import atan2, hypot, radians, sin, cos

from fire_route import select_crest_route
from fire_camera_capture import CAMERAS, FireCameraCapture, FFmpegSourceSink
from fire_capture_session import FireCaptureSession
from follow_controller import control_step


CASE_SUFFIX = "__traveling_follow_500ft"


def check_config(config):
    if config.get("selected_case_id", "").endswith(CASE_SUFFIX) is not True:
        raise ValueError("Runner is bound to the traveling 500 ft exact case")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-710", "C102304", "motor_vehicle_driver"):
        raise ValueError("Runner law/cell/actor identity differs")
    if config.get("fire_branch") != "traveling_follow" or config.get("target_distance_ft") != 500:
        raise ValueError("Runner branch or construction target differs")
    context = config.get("fire_context")
    if not isinstance(context, dict) or not context.get("alarm_response_source"):
        raise ValueError("Fire-alarm dispatch premise needs a named source")
    for key in ("apparatus_answered_alarm", "subject_authorized_emergency",
                "subject_official_business"):
        if type(context.get(key)) is not bool:
            raise ValueError("Fire context booleans must be explicit")
    if not isinstance(config.get("case", {}).get("recording_description"), dict):
        raise ValueError("Selected recording description is required")
    return True


def _spawn(world, blueprint_id, transform):
    blueprint = world.get_blueprint_library().find(blueprint_id)
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        raise ValueError("Native actor spawn failed: " + blueprint_id)
    return actor


def _cruise_apparatus(world_map, actor, carla):
    """Use the current Native lane tangent as a bounded steering command."""
    transform = actor.get_transform()
    waypoint = world_map.get_waypoint(transform.location)
    choices = [w for w in waypoint.next(6.) if w.road_id == waypoint.road_id
               and w.lane_id == waypoint.lane_id and not w.is_junction]
    if len(choices) != 1:
        raise ValueError("Apparatus lost its unique following lane")
    target = choices[0].transform.location
    difference = (target.x - transform.location.x, target.y - transform.location.y)
    if hypot(*difference) < 1:
        raise ValueError("Apparatus lane target collapsed")
    wanted = atan2(difference[1], difference[0])
    current = radians(transform.rotation.yaw)
    angle = atan2(sin(wanted-current), cos(wanted-current))
    velocity = actor.get_velocity()
    speed = hypot(velocity.x, velocity.y)
    error = 8.0 - speed
    throttle = min(.6, max(0., .2 * error))
    brake = min(.7, max(0., -.2 * error))
    actor.apply_control(carla.VehicleControl(throttle=throttle, brake=brake,
                                              steer=min(.5, max(-.5, angle / .6))))


def _device_readbacks(apparatus, carla):
    lights = apparatus.get_light_state()
    special = carla.VehicleLightState.Special1 | carla.VehicleLightState.Special2
    warning = bool(int(lights) & int(special))
    siren_getter = getattr(apparatus, "get_siren_state", None)
    if not callable(siren_getter):
        return warning, None
    siren = siren_getter()
    if type(siren) is not bool:
        raise ValueError("Native siren readback is not a boolean")
    return warning, siren


def run(output, host, port):
    import carla  # Native-only dependency.
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.native_output import seal_capture

    output = Path(output)
    config = json.loads((output / "config.json").read_text())
    check_config(config)
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original_settings = world.get_settings()
    owned = []
    sinks = {}
    camera = pipeline = session = None
    frames = []
    errors = []
    restored = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        route = select_crest_route(world.get_map(), target_gap_ft=500)
        apparatus = _spawn(world, "vehicle.carlamotors.firetruck",
                           route["apparatus"].transform)
        owned.append(apparatus)
        ego = _spawn(world, "vehicle.tesla.model3", route["ego"].transform)
        owned.append(ego)
        for name in CAMERAS:
            sinks[name] = FFmpegSourceSink(output, name)
        camera = FireCameraCapture(world, carla, ego, sinks)
        pipeline = PipelineCapture(client, ego, output, config["selected_case_id"],
                                   required_observations=config.get("required_atoms", []))
        session = FireCaptureSession(output, pipeline, ego, apparatus,
                                     config["fire_context"])
        start = None
        for _ in range(int(config.get("frames", 160))):
            _cruise_apparatus(world.get_map(), apparatus, carla)
            control_step(ego, apparatus, target_gap_ft=500,
                         carla_module=carla)
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError("World snapshot differs from completed Native tick")
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start
            camera.wait_for_frame(frame)
            warning, siren = _device_readbacks(apparatus, carla)
            session.capture(frame, time_s, warning_lamp_readback=warning,
                            siren_readback=siren)
            frames.append(frame)
        camera.verify_frames(frames)
    except BaseException as error:
        errors.append(str(error))
        raise
    finally:
        if session is not None:
            session.close()
        if pipeline is not None:
            pipeline.close(confirmed=not errors)
        if camera is not None:
            camera.close()
        for sink in sinks.values():
            sink.close()
        for actor in reversed(owned):
            actor.destroy()
        world.apply_settings(original_settings)
        current = world.get_settings()
        restored = (current.synchronous_mode == original_settings.synchronous_mode
                    and current.fixed_delta_seconds == original_settings.fixed_delta_seconds)
        if not restored:
            raise ValueError("Native world settings restoration readback differs")
    if errors or not frames:
        raise ValueError("Native capture did not finish")
    (output / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "original_frames": len(frames)}) + "\n")
    seal_capture(output, frames=len(frames), restoration={"restored": restored},
                 errors=[], encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={"native_map_name": world.get_map().name,
                          "route_road_id": route["road_id"],
                          "route_lane_id": route["lane_id"],
                          "crest_between_actors": True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        assert len(CAMERAS) == 4
        candidate = Path("config.json")
        if candidate.is_file():
            check_config(json.loads(candidate.read_text()))
        return
    if not args.output_dir:
        parser.error("--output-dir is required for Native capture")
    run(args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
