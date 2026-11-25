"""Borrow a surveyed CARLA world for one original pedestrian capture.

The caller owns actors, sensors, official signal readers and the world. This
module verifies the source binding and restores the borrowed simulation clock.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from carla_adapter import CarlaAdapter
from native_capture import DEFAULT_FRAMES, FPS, capture
from native_scene import SourceError, verify_site


def run_capture(world, *, attempt, site_ref, case_id, map_reader,
                walker, sensors, original_state_reader,
                walker_control_factory, vector_factory,
                expected_frames=DEFAULT_FRAMES):
    attempt = Path(attempt).resolve()
    path = (attempt / site_ref['path']).resolve()
    if not path.is_relative_to(attempt) or not path.is_file():
        raise SourceError('surveyed site source missing')
    if hashlib.sha256(path.read_bytes()).hexdigest() != site_ref['sha256']:
        raise SourceError('surveyed site source hash differs')
    site = json.loads(path.read_text(encoding='utf-8'))
    verify_site(site, attempt)
    road_source = site.get('road_xodr_source_path')
    if not isinstance(road_source, str) or road_source == 'road.xodr' or road_source not in {
            ref['path'] for ref in site['original_sources']}:
        raise SourceError('reviewed original OpenDRIVE map source missing')
    map_path = attempt / road_source
    loaded_map = map_reader(world)
    if type(loaded_map) is not bytes or hashlib.sha256(loaded_map).hexdigest() != hashlib.sha256(map_path.read_bytes()).hexdigest():
        raise SourceError('loaded Native map differs from surveyed original')
    original = copy.copy(world.get_settings())
    settings = copy.copy(original)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 1 / FPS
    adapter = CarlaAdapter(world, walker, sensors, original_state_reader,
                           walker_control_factory, vector_factory,
                           strict_actor_geometry=True)
    try:
        world.apply_settings(settings)
        readback = world.get_settings()
        if readback.synchronous_mode is not True or abs(readback.fixed_delta_seconds - 1 / FPS) > 1e-9:
            raise SourceError('Native 20 Hz synchronous clock readback failed')
        result = capture(site, site_ref, attempt, adapter, case_id, expected_frames)
    finally:
        try:
            adapter.close()
        finally:
            world.apply_settings(original)
    restored = world.get_settings()
    if (restored.synchronous_mode != original.synchronous_mode or
            restored.fixed_delta_seconds != original.fixed_delta_seconds):
        raise SourceError('borrowed Native world clock restoration failed')
    if map_reader(world) != loaded_map:
        raise SourceError('loaded Native map changed during capture')
    return result
