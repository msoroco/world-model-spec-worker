"""CARLA-lazy stopped fire-apparatus drive-to and parking construction.

This runner records original Native geometry and participant state. A commanded
centre distance and hand brake do not establish the observed statutory facts;
the saved finalizer measures them from retained original frames.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fire_route import select_crest_route
from fire_camera_capture import CAMERAS, FireCameraCapture, FFmpegSourceSink
from fire_capture_session import FireCaptureSession
from stopped_controller import control_step


ASSIGNMENT = "heldout__C102304__NRS-484B-710__motor_vehicle_driver"


def check_config(config):
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-710", "C102304", "motor_vehicle_driver"):
        raise ValueError("Stopped runner law/cell/actor identity differs")
    branch = config.get("fire_branch")
    target = config.get("target_distance_ft")
    if branch not in ("stopped_drive_to", "stopped_park") or target not in (450, 500, 550):
        raise ValueError("Stopped runner branch or numeric construction target differs")
    if config.get("selected_case_id") != ASSIGNMENT + "__" + branch + "_" + str(target) + "ft":
        raise ValueError("Stopped runner exact case identity differs")
    if config.get("rate_hz") != 20 or config.get("frames") != 160 or config.get("duration_s") != 8:
        raise ValueError("Stopped runner capture cadence/duration differs")
    if not isinstance(config.get("case", {}).get("recording_description"), dict):
        raise ValueError("Stopped runner recording description is missing")
    context = config.get("fire_context")
    if not isinstance(context, dict) or not context.get("alarm_response_source"):
        raise ValueError("Stopped apparatus alarm dispatch needs a named source")
    for key in ("apparatus_answered_alarm", "subject_authorized_emergency",
                "subject_official_business"):
        if type(context.get(key)) is not bool:
            raise ValueError("Stopped apparatus context booleans must be explicit")
    if context["apparatus_answered_alarm"] is not True:
        raise ValueError("Stopped branch requires authored answer-to-alarm premise")
    return True


def _spawn(world, blueprint_id, transform):
    actor = world.try_spawn_actor(world.get_blueprint_library().find(blueprint_id), transform)
    if actor is None:
        raise ValueError("Native actor spawn failed: " + blueprint_id)
    return actor


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
    from worker_exchange.native_output import seal_capture

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
        target = config["target_distance_ft"]
        # Start at least 100 ft beyond the requested centre distance so the
        # drive-to branch can have measured closing frames before arrival.
        route = select_crest_route(world.get_map(), target_gap_ft=target + 100)
        apparatus = _spawn(world, "vehicle.carlamotors.firetruck", route["apparatus"].transform)
        owned.append(apparatus)
        ego = _spawn(world, "vehicle.tesla.model3", route["ego"].transform)
        owned.append(ego)
        apparatus.apply_control(carla.VehicleControl(throttle=0., brake=1., hand_brake=True))
        for name in CAMERAS:
            sinks[name] = FFmpegSourceSink(output, name)
        camera = FireCameraCapture(world, carla, ego, sinks)
        pipeline = PipelineCapture(client, ego, output, config["selected_case_id"],
                                   required_observations=config.get("required_atoms", []))
        session = FireCaptureSession(output, pipeline, ego, apparatus, config["fire_context"])
        start = None
        for _ in range(config["frames"]):
            control_step(ego, apparatus, target_centre_ft=target,
                         park=config["fire_branch"] == "stopped_park",
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
        raise ValueError("Native stopped-apparatus capture did not finish")
    (output / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "original_frames": len(frames)}) + "\n")
    seal_capture(output, frames=len(frames), restoration={"restored": restored},
                 errors=[], encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={"native_map_name": world.get_map().name,
                          "route_road_id": route["road_id"],
                          "route_lane_id": route["lane_id"],
                          "crest_between_actors": True,
                          "stopped_apparatus_commanded": True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        assert len(CAMERAS) == 4
        config = Path("config.json")
        if config.is_file():
            check_config(json.loads(config.read_text()))
        return
    if not args.output_dir:
        parser.error("--output-dir is required for Native capture")
    run(args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
