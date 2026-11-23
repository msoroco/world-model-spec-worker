"""Lazy C227824 CARLA world lifecycle for one materialized Native attempt.

The operator supplies the CARLA endpoint and reviewed scene/map assets. This
module restores the prior world before calling the runtime's Native sealer.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from pathlib import Path

from native_attempt import run as run_ticks
from native_cameras import spawn as spawn_cameras
from native_packets import source_hashes
from native_recorder import FourStreamRecorder


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _private_root():
    source = Path(__file__).resolve()
    bundled = next((parent for parent in source.parents
                    if parent.name == ".runtime-work"), None)
    return bundled if bundled is not None else source.parents[2] / ".runtime-work"


def _materialized(scene, attempt):
    root = Path(attempt).resolve()
    if not root.is_dir() or not root.is_relative_to(_private_root().resolve()):
        raise ValueError("materialized Native attempt must be under .runtime-work")
    required = ("scene.json", "construction.json", "runner.py", "candidate-corridor.xodr")
    if any(not (root / name).is_file() for name in required):
        raise ValueError("materialized Native scene, runner, construction and map required")
    if json.loads((root / "scene.json").read_text()) != scene:
        raise ValueError("materialized Native scene differs")
    if scene.get("map_source_sha256") != _sha(root / "candidate-corridor.xodr"):
        raise ValueError("source-hashed original OpenDRIVE map differs")
    return root


def _spawn_walker(world, carla, scene):
    identity = scene.get("walker_blueprint_id")
    point = scene.get("walker_spawn_xyz_m")
    if not isinstance(identity, str) or not identity.startswith("walker.pedestrian."):
        raise ValueError("reviewed CARLA walker blueprint missing")
    if (not isinstance(point, list) or len(point) != 3 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in point)):
        raise ValueError("reviewed CARLA walker spawn missing")
    blueprint = world.get_blueprint_library().find(identity)
    if blueprint is None:
        raise ValueError("reviewed CARLA walker blueprint unavailable")
    transform = carla.Transform(carla.Location(x=point[0], y=point[1], z=point[2]),
                                carla.Rotation(yaw=scene.get("walker_spawn_yaw_deg", 0)))
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        raise ValueError("original CARLA walker spawn failed")
    return actor


def run_with_client(scene, attempt, client, carla, *, snapshot_world, restore_world,
                    seal_capture, camera_factory=spawn_cameras,
                    recorder_factory=FourStreamRecorder, walker_factory=_spawn_walker):
    """Injectable lifecycle seam; never seals a failed or unrestored capture."""
    root = _materialized(scene, attempt)
    prior = snapshot_world(client)
    world = None
    walker = None
    cameras = {}
    recorder = None
    capture = None
    failure = None
    cleanup = []
    restoration = {"restored": False}
    try:
        world = client.generate_opendrive_world((root / "candidate-corridor.xodr").read_text())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        if (world.get_settings().synchronous_mode is not True or
                abs(world.get_settings().fixed_delta_seconds - .05) > 1e-9):
            raise ValueError("original world did not read back 20 Hz synchronous mode")
        walker = walker_factory(world, carla, scene)
        cameras = camera_factory(world, carla, scene)
        recorder = recorder_factory(cameras, root)
        (root / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "native", "diagnostic_fixture": False,
            "case_id": scene["case_id"], "map_source_sha256": scene["map_source_sha256"]}) + "\n")
        capture = run_ticks(world, carla, scene, walker, recorder, root,
                            ticks=scene["planned_frames"])
    except BaseException as exc:
        failure = repr(exc)
    finally:
        if recorder is not None:
            try:
                recorder.close()
            except BaseException as exc:
                cleanup.append("recorder close: " + repr(exc))
        for sensor in reversed(list(cameras.values())):
            try:
                sensor.destroy()
            except BaseException as exc:
                cleanup.append("camera destroy: " + repr(exc))
        if walker is not None:
            try:
                walker.destroy()
            except BaseException as exc:
                cleanup.append("walker destroy: " + repr(exc))
        try:
            restoration = restore_world(client, prior)
        except BaseException as exc:
            cleanup.append("world restoration: " + repr(exc))
    if failure or cleanup or restoration.get("restored") is not True:
        (root / "native-run-status.json").write_text(json.dumps({
            "phase": "failed", "errors": [v for v in [failure, *cleanup] if v],
            "restoration": restoration}) + "\n")
        raise RuntimeError("Native C227824 acquisition or restoration failed")
    (root / "acquisition.json").write_text(json.dumps(source_hashes(root), indent=2) + "\n")
    seal_capture(root, frames=capture["frame_count"], restoration=restoration,
                 errors=[], encoder_exit_codes={name: 0 for name in cameras},
                 context={"case_id": scene["case_id"],
                          "map_source_sha256": scene["map_source_sha256"]})
    return {"case_id": scene["case_id"], "native_capture_sealed": True,
            "frames": capture["frame_count"], "physical_acceptance_claimed": False}


def run_native(scene, attempt, host="127.0.0.1", port=2000):
    """Production entrypoint; importing this module never imports CARLA."""
    root = _materialized(scene, attempt)
    output_root = (_private_root() / "c227824-runtime").resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(output_root)
    sys.dont_write_bytecode = True
    runtime = str(_private_root().parent / "runtime" / "scenario_pipeline")
    if runtime not in sys.path:
        sys.path.insert(0, runtime)
    import carla
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore
    client = carla.Client(host, port)
    client.set_timeout(30)
    return run_with_client(scene, root, client, carla, snapshot_world=snapshot,
                           restore_world=restore, seal_capture=seal_capture)
