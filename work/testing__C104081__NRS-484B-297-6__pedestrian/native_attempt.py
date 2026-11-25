"""Own one surveyed Native bypass attempt and restore its original world.

The caller supplies the live CARLA world, actor adapter, source reader and
camera recorder. This boundary never substitutes fixture data for acquisition.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import shutil

from delivery_audit import audit_saved
from native_construction import construct_native
from native_source_packet import capture_constructed_sources


def configure_original_clock(world) -> None:
    """Request and read back the fixed 20 Hz Native capture clock."""
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.05
    world.apply_settings(settings)
    actual = world.get_settings()
    delta = getattr(actual, "fixed_delta_seconds", None)
    if (getattr(actual, "synchronous_mode", None) is not True or
            type(delta) not in (int, float) or not math.isfinite(delta) or
            not math.isclose(delta, 0.05, abs_tol=1e-9)):
        raise ValueError("Native 20 Hz synchronous clock readback differs")


def run_native_attempt(client, carla, plan: dict, case_id: str, survey_path: Path,
                       survey_sha256: str, adapter, source_reader_factory,
                       camera_recorder, output: Path, *, restore_api,
                       camera_profile_sha256: str, traffic_plan_sha256: str,
                       pedestrian_blueprint: str, camera_rig=None,
                       camera_rig_factory=None, core_capture_factory=None,
                       walking_speed_m_s: float = 1.4) -> dict:
    """Capture, audit, destroy owned actors and verify original world restore.

    ``restore_api`` is the pinned runtime worker_exchange.world_restore module.
    The acquisition packet is never called physically accepted here. All
    restoration failures propagate; a success receipt requires readback.
    """
    if camera_recorder is None and camera_rig_factory is None:
        raise ValueError("four-camera original recorder required")
    if camera_rig is not None and camera_rig_factory is not None:
        raise ValueError("supply an owned rig or a factory, not both")
    output = Path(output)
    if output.exists() and any((output / name).exists() for name in
            ("capture", "source-packet.json", "result.json", "trace.jsonl",
             "video_frames.jsonl", "capture-seal.json")):
        raise ValueError("Native attempt output already has acquisition evidence")
    saved = restore_api.snapshot(client)
    constructed = None
    primary_error = None
    cleanup_errors = []
    receipt = None
    core_capture = None
    packet_output = output.parent / (output.name + "-packet-stage")
    if packet_output.exists():
        raise ValueError("Native packet staging path must be fresh")
    try:
        world = client.get_world()
        configure_original_clock(world)
        if camera_rig_factory is not None:
            camera_rig = camera_rig_factory(world)
            camera_recorder = camera_rig.recorder
        if camera_recorder is None:
            raise ValueError("four-camera original recorder required")
        constructed = construct_native(plan, case_id, Path(survey_path),
                                       survey_sha256, adapter)
        owned = constructed["owned_handles"]
        walker = owned[-1]
        source_reader = source_reader_factory(world, walker, constructed,
                                              camera_recorder)
        if not callable(source_reader):
            raise ValueError("synchronized original source reader required")
        if core_capture_factory is not None:
            core_capture = core_capture_factory(client, walker, output, case_id)
        capture_constructed_sources(
            world, walker, carla, constructed, Path(survey_path), case_id,
            source_reader, packet_output, camera_profile_sha256=camera_profile_sha256,
            traffic_plan_sha256=traffic_plan_sha256,
            pedestrian_blueprint=pedestrian_blueprint,
            speed_m_s=walking_speed_m_s,
            camera_recorder=camera_recorder,
            on_core_sample=core_capture.capture if core_capture is not None else None,
        )
        if core_capture is not None:
            core_capture.close(confirmed=True)
        output.mkdir(parents=True, exist_ok=True)
        for source in packet_output.iterdir():
            destination = output / source.name
            if destination.exists():
                if source.name != "site-survey.json" or \
                        hashlib.sha256(source.read_bytes()).digest() != \
                        hashlib.sha256(destination.read_bytes()).digest():
                    raise ValueError("original Core and pedestrian source collision")
                source.unlink()
                continue
            source.replace(destination)
        packet_output.rmdir()
        audit = audit_saved(output, case_id, decode_media=True)
        if not audit["checks"]["full_video_decode"]:
            raise ValueError("full saved camera decode required")
        packet_sha256 = hashlib.sha256((output / "source-packet.json").read_bytes()).hexdigest()
        if audit.get("source_packet_sha256") != packet_sha256:
            raise ValueError("saved audit and Native source packet seal differ")
        receipt = {"format": "worker-pedestrian-native-attempt-lifecycle",
                   "case_id": case_id, "source_packet_sha256": packet_sha256,
                   "saved_audit": audit, "physical_acceptance": "not_assessed"}
    except BaseException as exc:
        primary_error = exc
    finally:
        if core_capture is not None:
            try:
                core_capture.close(confirmed=primary_error is None)
            except BaseException as exc:
                cleanup_errors.append(f"Core capture close: {exc}")
        if primary_error is not None and camera_recorder is not None:
            try:
                camera_recorder.abort()
            except BaseException as exc:
                cleanup_errors.append(f"camera encoder abort: {exc}")
        if constructed is not None:
            for handle in reversed(constructed["owned_handles"]):
                try:
                    adapter.destroy(handle)
                except BaseException as exc:
                    cleanup_errors.append(f"actor destruction: {exc}")
        if camera_rig is not None:
            try:
                camera_rig.close()
            except BaseException as exc:
                cleanup_errors.append(f"camera actor destruction: {exc}")
        try:
            restored = restore_api.restore(client, saved)
            if restored.get("restored") is not True:
                cleanup_errors.append("world restore lacked positive readback")
        except BaseException as exc:
            cleanup_errors.append(f"world restore: {exc}")
    if cleanup_errors:
        raise RuntimeError("Native cleanup failed: " + "; ".join(cleanup_errors)) from primary_error
    if primary_error is not None:
        raise primary_error
    receipt["world_restore"] = restored
    (output / "lifecycle-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
