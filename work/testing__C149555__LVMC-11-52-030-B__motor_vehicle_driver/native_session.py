"""Own one freight Native capture session and restore the CARLA world."""

from __future__ import annotations

import copy
import os
from pathlib import Path

from freight_contract import SourceError, prepare_scene


def capture_session(client, site: dict, dossier: dict, *, case_id: str,
                    variant: str, output: Path, adapter_factory=None,
                    camera_rig_factory=None, pipeline_capture_class=None,
                    frame_capture=None, encoder=None, composer=None,
                    world_restore_module=None, scene_preparer=None) -> dict:
    if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT"):
        raise SourceError("SCENARIO_PIPELINE_OUTPUT_ROOT must be set before runtime imports")
    if adapter_factory is None:
        from carla_adapter import NativeCarlaAdapter
        adapter_factory = NativeCarlaAdapter
    if camera_rig_factory is None:
        from camera_rig import CameraRig
        camera_rig_factory = CameraRig
    if pipeline_capture_class is None:
        from pipeline_capture import PipelineCapture
        pipeline_capture_class = PipelineCapture
    if frame_capture is None:
        from native_capture import capture_original_frames
        frame_capture = capture_original_frames
    if encoder is None:
        from encode_cameras import encode_cameras
        encoder = encode_cameras
    if composer is None:
        from scenario_pipeline.worker_exchange.media import compose_four_views
        composer = compose_four_views
    if world_restore_module is None:
        from scenario_pipeline.worker_exchange import world_restore
        world_restore_module = world_restore
    scene_preparer = scene_preparer or prepare_scene
    output = Path(output)
    if not output.is_dir():
        raise SourceError("materialized Native output directory missing")
    saved = world_restore_module.snapshot(client)
    adapter = None
    failure = None
    result = None
    restoration = None
    try:
        world = client.get_world()
        settings = copy.copy(world.get_settings())
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        adapter = adapter_factory(world, site, dossier)
        scene_preparer(adapter, site, variant, dossier)
        if adapter.ego is None:
            raise SourceError("freight Native ego was not spawned")
        with camera_rig_factory(adapter, site) as cameras:
            with pipeline_capture_class(client, adapter.ego, output, case_id) as native:
                rows = frame_capture(adapter, adapter.sample_original, output,
                                     case_id=case_id, read_camera=cameras.read_camera,
                                     native_capture=native)
        media = encoder(output)
        composition = composer({name: output / ref["path"] for name, ref in media.items()},
                               output / "frame-map.jsonl", output / "raw.mkv")
        result = {"frames": len(rows), "media": media, "composition": composition}
    except BaseException as error:
        failure = error
        raise
    finally:
        cleanup_error = None
        if adapter is not None:
            try:
                adapter.cleanup()
            except BaseException as error:
                cleanup_error = error
        try:
            restoration = world_restore_module.restore(client, saved)
        except BaseException as error:
            if failure is None and cleanup_error is None:
                raise
            cleanup_error = cleanup_error or error
        if failure is None and cleanup_error is not None:
            raise SourceError("Native cleanup or world restoration failed") from cleanup_error
    return dict(result, restoration=restoration)
