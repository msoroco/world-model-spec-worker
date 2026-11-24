"""Source-gated Native actor and camera construction for C109749.

The source packet and spawn plan must be retained under the attempt. This
checks identity and cleanup, not whether a legal highway designation is true.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from center_lane_site import validate_site
from native_capture import CAMERA_DIMENSIONS, VIEWS

ASSIGNMENT = 'testing__C109749__NRS-484B-223-3c__motor_vehicle_driver'
SUFFIXES = ('below_50ft', 'at_50ft', 'above_50ft', 'no_merge')


def _source(root, binding):
    if not isinstance(binding, dict) or set(binding) != {'path', 'sha256'}:
        raise ValueError('reviewed source binding missing')
    relative = binding['path']
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
            or '..' in Path(relative).parts):
        raise ValueError('reviewed source path invalid')
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
        raise ValueError('reviewed source missing or linked')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != binding['sha256']:
        raise ValueError('reviewed source bytes differ')
    return raw


class NativeScene:
    def __init__(self, ego, receiving_vehicle, cameras, plan_sha256):
        self.ego = ego
        self.receiving_vehicle = receiving_vehicle
        self.cameras = cameras
        self.plan_sha256 = plan_sha256
        self.closed = False

    def close(self):
        if self.closed:
            return
        self.closed = True
        first_error = None
        for sensor in self.cameras.values():
            try:
                sensor.stop()
            except Exception as error:
                if first_error is None:
                    first_error = error
        for actor in reversed([self.ego, self.receiving_vehicle, *self.cameras.values()]):
            try:
                actor.destroy()
            except Exception as error:
                if first_error is None:
                    first_error = error
        if first_error is not None:
            raise first_error


def spawn_scene(world, attempt_root, case_id, site, plan_binding, transform_factory):
    if case_id not in {ASSIGNMENT + '__' + suffix for suffix in SUFFIXES}:
        raise ValueError('wrong exact center-lane case')
    root = Path(attempt_root).resolve()
    validated = validate_site(site)
    map_source = json.loads(_source(root, validated['native_map_source']))
    _source(root, validated['highway_review_source'])
    current_map = world.get_map()
    if (not isinstance(map_source, dict) or
            map_source.get('opendrive_sha256') != hashlib.sha256(
                current_map.to_opendrive().encode()).hexdigest()):
        raise ValueError('live OpenDRIVE differs from reviewed Native map source')
    settings = world.get_settings()
    if settings.synchronous_mode is not True or abs(settings.fixed_delta_seconds - .05) > 1e-8:
        raise ValueError('Native world requires synchronous 20 Hz settings')
    plan_bytes = _source(root, plan_binding)
    plan = json.loads(plan_bytes)
    if (not isinstance(plan, dict) or plan.get('case_id') != case_id or
            set(plan.get('vehicles', {})) != {'ego', 'receiving'} or
            set(plan.get('cameras', {})) != set(VIEWS) or
            not isinstance(plan.get('route_xy_m'), list) or
            len(plan['route_xy_m']) < 3):
        raise ValueError('exact four-camera spawn plan missing')
    library = world.get_blueprint_library()
    spawned = []
    try:
        vehicles = {}
        for role in ('ego', 'receiving'):
            spec = plan['vehicles'][role]
            if (not isinstance(spec, dict) or not isinstance(spec.get('blueprint_id'), str)
                    or not spec['blueprint_id'].startswith('vehicle.')
                    or not isinstance(spec.get('transform'), dict)):
                raise ValueError('original vehicle spawn spec missing')
            actor = world.spawn_actor(library.find(spec['blueprint_id']),
                                      transform_factory(spec['transform']))
            if actor is None or type(getattr(actor, 'id', None)) is not int or actor.id <= 0:
                raise ValueError('original vehicle spawn failed')
            spawned.append(actor)
            vehicles[role] = actor
        if vehicles['ego'].id == vehicles['receiving'].id:
            raise ValueError('original vehicles share identity')
        cameras = {}
        for view in VIEWS:
            spec = plan['cameras'][view]
            if (not isinstance(spec, dict) or spec.get('blueprint_id') != 'sensor.camera.rgb'
                    or not isinstance(spec.get('transform'), dict)):
                raise ValueError('original camera spawn spec missing: ' + view)
            blueprint = library.find('sensor.camera.rgb')
            width, height = CAMERA_DIMENSIONS[view]
            blueprint.set_attribute('image_size_x', str(width))
            blueprint.set_attribute('image_size_y', str(height))
            blueprint.set_attribute('sensor_tick', '0.05')
            sensor = world.spawn_actor(blueprint, transform_factory(spec['transform']),
                                       attach_to=vehicles['ego'])
            if sensor is None or type(getattr(sensor, 'id', None)) is not int or sensor.id <= 0:
                raise ValueError('original camera spawn failed: ' + view)
            spawned.append(sensor)
            cameras[view] = sensor
        return NativeScene(vehicles['ego'], vehicles['receiving'], cameras,
                           hashlib.sha256(plan_bytes).hexdigest()), plan['route_xy_m']
    except Exception:
        for actor in reversed(spawned):
            if hasattr(actor, 'stop'):
                try:
                    actor.stop()
                except Exception:
                    pass
            try:
                actor.destroy()
            except Exception:
                pass
        raise


def run_scene_capture(*, world, attempt_root, case_id, site, plan_binding,
                      transform_factory, control_factory, count=900, dimensions=None):
    """Spawn, drive, seal and release one original attempt.

    The caller owns the existing world lease and settings. Default duration is
    the production 900 frames; dimensions may differ only in CPU diagnostics.
    """
    from carla_runner import run_capture

    scene, route = spawn_scene(world, attempt_root, case_id, site,
                               plan_binding, transform_factory)
    try:
        receipt = run_capture(attempt_root=attempt_root, case_id=case_id, site=site,
                              world=world, ego=scene.ego,
                              receiving_vehicle=scene.receiving_vehicle,
                              cameras=scene.cameras, route_xy_m=route,
                              control_factory=control_factory, count=count,
                              dimensions=dimensions)
        return {'capture_receipt': receipt, 'spawn_plan_sha256': scene.plan_sha256,
                'physical_acceptance_claimed': False}
    finally:
        scene.close()
