"""Source-gated Native acquisition for the four exact dual-green cases.

An independent observer publishes frame-keyed lamp packets while this runner
records the original four views. Its source directory is supplied through
SCENARIO_DUAL_GREEN_SOURCE_ROOT. The runner never decides lawful use or yields.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from dual_green import check_site, construct_native, read_source, require
from native_attempt import run_native_attempt
from native_cameras import CameraCapture
from native_other_controller import OtherUserController
from native_straight_controller import for_exact_case


def _copy_ref(source, output, ref):
    original = read_source(source, ref)
    target = output / ref["path"]
    require(target.resolve().is_relative_to(output.resolve()),
            "original source escapes attempt")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        require(hashlib.sha256(target.read_bytes()).hexdigest() == ref["sha256"],
                "original source collision")
    else:
        shutil.copyfile(original, target)
    require(hashlib.sha256(target.read_bytes()).hexdigest() == ref["sha256"],
            "original source changed while copying")
    return ref


def _live_packet(source, output, name, frame, user=None):
    path = source / name
    deadline = time.monotonic() + 15
    while not path.is_file() and time.monotonic() < deadline:
        time.sleep(.02)
    require(path.is_file(), "independent original packet missing for frame")
    packet = json.loads(path.read_text(encoding="utf-8"))
    require(packet.get("frame") == frame, "independent original packet frame mismatch")
    if user is not None:
        require(str(packet.get("user_id")) == user,
                "independent lawful-use packet identity mismatch")
    else:
        observed = packet.get("original_observation")
        require(isinstance(observed, dict), "independent original lamp image missing")
        observed_path = (output / observed["path"]).resolve()
        require(observed_path.is_relative_to(output.resolve()),
                "original lamp image escapes attempt")
        if not observed_path.is_file():
            _copy_ref(source, output, observed)
        read_source(output, observed)
        require(packet.get("observer_method") in
                ("independent_camera_frame_review", "independent_physical_lamp_sensor"),
                "independent original lamp observer missing")
    ref = {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return _copy_ref(source, output, ref)


def _readback(settings):
    return (settings.synchronous_mode, settings.fixed_delta_seconds,
            settings.no_rendering_mode)


def run(host, port, output_dir, case_id):
    source_name = os.environ.get("SCENARIO_DUAL_GREEN_SOURCE_ROOT")
    require(source_name, "Reviewed original dual-aspect source root required")
    source = Path(source_name).resolve()
    output = Path(output_dir).resolve()
    require(source.is_dir() and output.is_dir() and source != output,
            "Reviewed original dual-aspect source root invalid")
    site_source = source / "site.json"
    require(site_source.is_file(), "Reviewed original dual-aspect site missing")
    site = json.loads(site_source.read_text(encoding="utf-8"))
    require(not (output / "site.json").exists(), "site source shadows construction")
    shutil.copyfile(site_source, output / "site.json")
    for ref in site["original_sources"]:
        _copy_ref(source, output, ref)
    check_site(site, output)
    require(type(port) is int and port > 0 and host, "Native host/port missing")
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture

    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    original_settings = world.get_settings()
    original_map = world.get_map().name
    require(original_map == site["native_map_name"], "surveyed Native map unavailable")
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = .05
    settings.no_rendering_mode = False
    actors = []
    cameras = None
    capture = None
    completed = False
    errors = []
    try:
        world.apply_settings(settings)
        blueprints = world.get_blueprint_library()
        ego_blueprint = blueprints.find(site["ego_blueprint_id"])
        require(ego_blueprint is not None, "surveyed ego blueprint absent")
        other_kind = None if case_id.endswith("__dual_clear") else site["other_user_kind"]
        other_blueprint = None if other_kind is None else blueprints.find(
            site["other_user_blueprint_id"])
        scene = construct_native(site, output, world, carla, ego_blueprint,
                                 other_blueprint, other_kind)
        actors = scene["actors"]
        cameras = CameraCapture(world, actors[0], site, output, carla)
        capture = PipelineCapture(client, actors[0], output, case_id)
        controller = for_exact_case(case_id, site, output, carla, actors)
        other_controller = None if other_kind is None else OtherUserController(
            case_id, site, output, carla, actors[1])

        def lamp(frame):
            return _live_packet(source, output, f"lamp-{frame}.json", frame)

        def lawful(frame, user):
            return _live_packet(source, output, f"lawful-{frame}-{user}.json",
                                frame, user)

        run_native_attempt(site, output, world, actors, controller, lamp, lawful,
                           output, case_id, 900, camera_frame_for_tick=cameras.append,
                           other_controller=other_controller,
                           capture_after_tick=capture.capture)
        completed = True
    except BaseException as error:
        errors.append(repr(error))
        raise
    finally:
        if capture is not None:
            try: capture.close(confirmed=completed)
            except BaseException as error: errors.append(repr(error))
        if cameras is not None:
            try: cameras.close()
            except BaseException as error: errors.append(repr(error))
        for actor in reversed(actors):
            try: actor.destroy()
            except BaseException as error: errors.append(repr(error))
        try:
            world.apply_settings(original_settings)
        except BaseException as error:
            errors.append(repr(error))
    restored = world.get_map().name == original_map and _readback(
        world.get_settings()) == _readback(original_settings)
    require(completed and restored and not errors,
            "Native capture did not close and restore cleanly")
    from saved_finalizer import finalize
    finalize(output / "site.json", output, output, case_id,
             output / "saved-observation.json")
    subprocess.run([sys.executable, str(output / "analysis.py"),
                    "--attempt", str(output), "--output",
                    str(output / "analysis-report.json")], check=True)
    seal_capture(output, frames=900,
                 restoration={"restored": True,
                              "settings_readback": "original map and world settings restored"},
                 errors=[], encoder_exit_codes={name: 0 for name in
                                               ("overview", "approach", "reference_corner",
                                                "driver_reference")},
                 context={"case_id": case_id,
                          "site_sha256": hashlib.sha256((output / "site.json").read_bytes()).hexdigest()})
