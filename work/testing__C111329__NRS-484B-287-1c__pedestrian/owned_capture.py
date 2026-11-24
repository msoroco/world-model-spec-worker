"""Bind source-checked pedestrian route control to original-frame capture.

The caller supplies real CARLA objects and frame-synchronous readers. This
module owns walker cleanup, but makes no legal or physical acceptance claim.
"""

from pathlib import Path

from native_observation import capture_observation
from native_route import advance_pedestrian, spawn_pedestrian


def capture_owned(world, packet: dict, case_id: str, output: str | Path,
                  read_device, camera_readers: dict, *, carla_module=None,
                  ticks: int = 900, camera_dimensions=None) -> dict:
    """Apply route control immediately before every Native world tick."""
    walker = spawn_pedestrian(world, packet, carla_module=carla_module)
    target_index = 1

    def before_tick():
        nonlocal target_index
        target_index = advance_pedestrian(walker, packet, target_index,
                                          carla_module=carla_module)

    try:
        return capture_observation(world, walker, packet, case_id, output,
                                   read_device, ticks=ticks,
                                   camera_readers=camera_readers,
                                   camera_dimensions=camera_dimensions,
                                   before_tick=before_tick)
    finally:
        walker.destroy()
