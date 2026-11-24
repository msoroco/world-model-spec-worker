"""Borrow a CARLA world for one source-bound, synchronous door capture.

The caller supplies the actual actor factory and independent original-act
observer. This runner only manages the map and clock boundary; it cannot
turn a requested door action into an observed physical or legal outcome.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from carla_adapter import CarlaDoorAdapter
from native_capture import RATE_HZ, capture
from native_output_bridge import publish
from analysis import analyze
from site_contract import read_packet


def run_capture(world, carla_module, *, survey_path: Path, survey_sha256: str,
                case_id: str, output: Path, map_reader, actor_factory,
                driver_act_controller, original_observer) -> dict:
    """Capture with a source-hashed map and restore the borrowed world clock."""
    packet = read_packet(survey_path, survey_sha256)

    def map_digest():
        source = map_reader(world)
        if type(source) is not bytes or not source:
            raise ValueError("original loaded map bytes are missing")
        return hashlib.sha256(source).hexdigest()

    if map_digest() != packet["map_sha256"]:
        raise ValueError("loaded map bytes differ from surveyed source")
    original = copy.copy(world.get_settings())
    settings = copy.copy(original)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 1 / RATE_HZ
    adapter = CarlaDoorAdapter(
        world, carla_module, map_sha256=map_digest,
        actor_factory=actor_factory,
        driver_act_controller=driver_act_controller,
        original_observer=original_observer)
    result = None
    try:
        world.apply_settings(settings)
        readback = world.get_settings()
        if (readback.synchronous_mode is not True or
                abs(readback.fixed_delta_seconds - 1 / RATE_HZ) > 1e-9):
            raise ValueError("Native 20 Hz synchronous clock readback failed")
        result = capture(adapter, survey_path=survey_path,
                         survey_sha256=survey_sha256, case_id=case_id,
                         output=output)
    finally:
        # CARLA world settings belong to the caller even when capture fails.
        try:
            adapter.cleanup()
        finally:
            world.apply_settings(original)
    restored = world.get_settings()
    if (restored.synchronous_mode != original.synchronous_mode or
            restored.fixed_delta_seconds != original.fixed_delta_seconds):
        raise ValueError("Native world restoration readback failed")
    source = map_reader(world)
    if type(source) is not bytes or hashlib.sha256(source).hexdigest() != packet["map_sha256"]:
        raise ValueError("loaded map bytes changed before publication")
    seal = publish(output, map_bytes=source, restoration_verified=True)
    analyze(output, output / "analysis-report.json")
    return dict(result, capture_seal_sha256=hashlib.sha256(seal.read_bytes()).hexdigest())
