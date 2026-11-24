"""Source-gated Native session for one exact right-pass attempt.

Operator callbacks construct actors, sensors and controls from a reviewed map
packet. Their requests remain distinct from the original sampled behavior.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from pass_right_actor import make_actor_sampler
from pass_right_capture import CAMERAS
from pass_right_route import build_case, load_map_packet
from pass_right_sensor import capture_native_attempt


def run_session(world, *, packet_path: Path, packet_sha256: str, variant: str,
                attempt: Path, map_reader, spawn_actors, spawn_sensors,
                controller_factory, frame_map, left_signal_mask: int,
                diagnostic_profile=None, frame_count: int = 900) -> dict:
    """Acquire original sources and restore every borrowed Native world setting.

    ``map_reader(world)`` returns the original loaded OpenDRIVE bytes. The
    packet must name their SHA256, not a display map name. Factories return
    newly owned actors/sensors, all destroyed even after acquisition failure.
    """
    packet = load_map_packet(Path(packet_path), packet_sha256)
    case = build_case(packet, variant)

    def map_digest():
        source = map_reader(world)
        if type(source) is not bytes or not source:
            raise ValueError('original loaded map bytes required')
        return hashlib.sha256(source).hexdigest()

    expected_map = packet.get('source_opendrive_sha256')
    if not isinstance(expected_map, str) or map_digest() != expected_map:
        raise ValueError('loaded original map differs from sealed source packet')
    attempt = Path(attempt)
    if attempt.exists() and any(attempt.iterdir()):
        raise ValueError('fresh Native attempt directory required')
    attempt.mkdir(parents=True, exist_ok=True)
    original = copy.copy(world.get_settings())
    settings = copy.copy(original)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = .05
    owned = []
    try:
        world.apply_settings(settings)
        readback = world.get_settings()
        if readback.synchronous_mode is not True or abs(readback.fixed_delta_seconds - .05) > 1e-9:
            raise ValueError('Native synchronous 20 Hz clock readback failed')
        ego, target = spawn_actors(world, packet, case)
        owned.extend((ego, target))
        if not all(getattr(actor, 'is_alive', False) for actor in (ego, target)):
            raise ValueError('original actors not alive')
        sampler = make_actor_sampler(packet, ego, target,
                                     left_signal_mask=left_signal_mask)
        sensors = spawn_sensors(world, ego, target, packet, case)
        if not isinstance(sensors, dict) or set(sensors) != set(CAMERAS):
            raise ValueError('four original camera sensors required')
        owned.extend(sensors.values())
        controller = controller_factory(world, ego, target, packet, case)
        if not callable(controller):
            raise ValueError('Native actor controller required')
        acquired = capture_native_attempt(
            world, sensors, sampler, packet, ego.id, target.id,
            frame_map, attempt, frame_count=frame_count,
            diagnostic_profile=diagnostic_profile, before_tick=controller)
        if map_digest() != expected_map:
            raise ValueError('loaded original map changed during attempt')
        trace_bytes = (json.dumps(acquired['trace'], sort_keys=True,
                                  separators=(',', ':')) + '\n').encode()
        (attempt / 'trace.json').write_bytes(trace_bytes)
        return {'variant': variant, 'packet_sha256': packet_sha256,
                'map_sha256': expected_map,
                'trace_sha256': hashlib.sha256(trace_bytes).hexdigest(),
                'camera_sources': acquired['cameras'],
                'diagnostic_profile': acquired['diagnostic_profile'],
                'physical_acceptance_claimed': False}
    finally:
        try:
            for actor in reversed(owned):
                if actor is not None:
                    if hasattr(actor, 'stop'):
                        actor.stop()
                    actor.destroy()
        finally:
            world.apply_settings(original)
