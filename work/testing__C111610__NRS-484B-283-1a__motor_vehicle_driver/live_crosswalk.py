"""Own a synchronous Native crosswalk attempt and seal its source files.

The injected factory must construct source-reviewed actors, sensors, controller
and camera readers. This module handles world timing, actor ownership and
cleanup around the existing original-frame capture writer.
"""
from __future__ import annotations

from pathlib import Path

from carla_adapter import CarlaNativeAdapter
from native_capture import CAMERAS, capture


def run(client, scene_path, site_path, exception_path, output, scene_factory,
        *, dimensions=None):
    world = client.get_world()
    previous = world.get_settings()
    if not callable(scene_factory):
        raise ValueError('Native crosswalk scene factory required')
    owned = []
    def register(actor):
        if actor is None or any(actor is prior for prior in owned):
            raise ValueError('distinct live Native actor required')
        owned.append(actor)
        return actor
    settings_changed = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        settings_changed = True
        scene = scene_factory(world=world, scene_path=Path(scene_path),
                              site_path=Path(site_path),
                              exception_path=Path(exception_path),
                              register=register)
        if not isinstance(scene, dict) or set(scene) != {
                'ego', 'pedestrian', 'sensors', 'camera_readers', 'controller'}:
            raise ValueError('complete original crosswalk scene required')
        if not isinstance(scene['sensors'], dict) or set(scene['sensors']) != set(CAMERAS):
            raise ValueError('four original camera sensor actors required')
        returned = [scene['ego'], scene['pedestrian'], *scene['sensors'].values()]
        if len(owned) != 6 or {id(actor) for actor in returned} != {id(actor) for actor in owned}:
            raise ValueError('six distinct registered Native participant/sensor actors required')
        if not isinstance(scene['camera_readers'], dict) or set(scene['camera_readers']) != set(CAMERAS):
            raise ValueError('four original camera readers required')
        adapter = CarlaNativeAdapter(world, scene['ego'], scene['pedestrian'],
                                     scene['camera_readers'], site_path,
                                     source_ref='original_native_crosswalk',
                                     controller=scene['controller'])
        index = capture(adapter, scene_path, site_path, exception_path, output,
                        dimensions=dimensions)
        return {'case_id': index['case_id'], 'source_index': str(Path(output) / 'source-index.json'),
                'physical_acceptance': 'unverified'}
    finally:
        for actor in reversed(owned):
            try:
                actor.destroy()
            except Exception:
                pass
        if settings_changed:
            world.apply_settings(previous)
