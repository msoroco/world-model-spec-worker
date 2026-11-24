"""Own one source-bound Native blind-person encounter and restore the world.

The caller supplies the pinned world_restore API and independently reviewed
source packet. This module does not acquire or certify blindness evidence.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from blind_encounter import construct_native
from native_capture import capture_reviewed
from reviewed_sources import prepare


def configure_clock(world) -> None:
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.05
    world.apply_settings(settings)
    actual = world.get_settings()
    delta = getattr(actual, "fixed_delta_seconds", None)
    if (actual.synchronous_mode is not True or type(delta) not in (int, float)
            or not math.isfinite(delta) or abs(delta - 0.05) > 1e-9):
        raise ValueError("Native 20 Hz clock readback differs")


def run_native_attempt(client, source_packet: Path, output: Path, *,
                       construction_adapter_factory, capture_adapter_factory,
                       restore_api) -> dict:
    """Capture with exact reviewed identities; always destroy and restore.

    The construction adapter owns spawns for the source-reviewed vehicle,
    protected person and cue. The capture adapter owns original cameras and
    the synchronized observation reader. Each factory receives the live world.
    """
    source_packet = Path(source_packet)
    plan = prepare(source_packet)
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Native attempt output must be empty")
    saved = restore_api.snapshot(client)
    constructed = None
    construction_adapter = None
    capture_adapter = None
    primary_error = None
    cleanup_errors = []
    result = None
    restored = None
    try:
        world = client.get_world()
        if world.get_map().name != plan["map_id"]:
            raise ValueError("live Native map differs from reviewed route")
        configure_clock(world)
        construction_adapter = construction_adapter_factory(world, plan)
        constructed = construct_native(construction_adapter, plan)
        capture_adapter = capture_adapter_factory(world, plan, constructed)
        if capture_adapter is None:
            raise ValueError("original camera and observation adapter required")
        result = capture_reviewed(capture_adapter, plan["case_id"], output,
                                  source_packet=source_packet)
        if result.get("reviewed_source_bindings") != plan["reviewed_source_bindings"]:
            raise ValueError("captured reviewed sources differ from launch")
    except BaseException as exc:
        primary_error = exc
    finally:
        if capture_adapter is not None:
            try:
                capture_adapter.emergency_stop()
                capture_adapter.close()
            except BaseException as exc:
                cleanup_errors.append(f"capture adapter cleanup: {exc}")
        if constructed is not None:
            for handle in reversed(constructed["owned_handles"]):
                try:
                    construction_adapter.destroy_actor(handle)
                except BaseException as exc:
                    cleanup_errors.append(f"owned actor cleanup: {exc}")
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
    receipt = {"format": "worker-blind-person-native-lifecycle",
               "case_id": plan["case_id"],
               "reviewed_source_bindings": plan["reviewed_source_bindings"],
               "original_frame_count": result["original_frame_count"],
               "world_restore": restored,
               "lifecycle_events": ["capture_finished", "encoders_closed",
                                    "restoration_verified", "native_exit"],
               "physical_acceptance": "not_assessed"}
    output.mkdir(parents=True, exist_ok=True)
    with (output / "lifecycle-receipt.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def handoff_after_release(receipt: dict, owner_release, saved_processing) -> list[str]:
    """Prove saved processing starts only after Native ownership is released.

    The local operator supplies the canonical release and saved-only calls.
    Both must succeed; this function cannot fabricate a physical recording.
    """
    expected = ["capture_finished", "encoders_closed", "restoration_verified", "native_exit"]
    if receipt.get("lifecycle_events") != expected or receipt.get("world_restore", {}).get("restored") is not True:
        raise ValueError("Native closure and world restoration required before release")
    if owner_release(receipt) is not True:
        raise ValueError("Native owner release did not succeed")
    events = expected + ["owner_released"]
    saved_processing(receipt)
    events.append("saved_processing_started")
    return events
