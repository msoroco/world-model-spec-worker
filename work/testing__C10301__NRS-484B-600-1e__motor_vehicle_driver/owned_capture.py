"""Operator-owned world lifecycle for one exact C10301 Native speed attempt.

The caller supplies an existing CARLA client and reviewed site packet. This
wrapper never allocates a server and restores map, settings and weather even
when construction, capture or saved finalization fails.
"""
from __future__ import annotations

import copy

from native_capture import capture


def capture_owned(client, packet_path, attempt, case_id, native_run_id,
                  uncertainty_mps, transform_factory, control_factory, *,
                  diagnostic_fixture=False, media_factory=None):
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    saved = snapshot(client)
    try:
        world = client.get_world()
        settings = copy.copy(world.get_settings())
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        current = world.get_settings()
        if (current.synchronous_mode is not True or
                abs(current.fixed_delta_seconds - 0.05) > 1e-9):
            raise ValueError('Native world 20 Hz settings readback differs')
        kwargs = {'diagnostic_fixture': diagnostic_fixture}
        if not diagnostic_fixture:
            kwargs['client'] = client
        if media_factory is not None:
            kwargs['media_factory'] = media_factory
        return capture(world, packet_path, attempt, case_id, native_run_id,
                       uncertainty_mps, transform_factory, control_factory, **kwargs)
    finally:
        restore(client, saved)
