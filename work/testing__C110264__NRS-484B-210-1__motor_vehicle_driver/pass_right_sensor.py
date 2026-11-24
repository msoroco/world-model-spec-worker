"""Capture four original CARLA camera streams on one Native frame clock.

The caller owns CARLA actor construction, world restoration, and the source
map/road review. This adapter imports no CARLA module and runs only on request.
Archives remain in the attempt scratch directory, never in the worker return.
"""
from __future__ import annotations

import hashlib
import io
from contextlib import ExitStack
from pathlib import Path
from queue import Empty, Queue
from zipfile import ZIP_STORED, ZipFile

from PIL import Image

from pass_right_capture import CAMERAS, collect_native_trace
from pass_right_media import PROFILE


def _png_from_native(image: object, dimensions: tuple[int, int]) -> bytes:
    width, height = dimensions
    if image.width != width or image.height != height:
        raise ValueError('original camera dimensions differ from profile')
    raw = bytes(image.raw_data)
    if len(raw) != width * height * 4:
        raise ValueError('original camera BGRA buffer length mismatch')
    output = io.BytesIO()
    Image.frombytes('RGBA', dimensions, raw, 'raw', 'BGRA').convert('RGB').save(
        output, format='PNG')
    return output.getvalue()


def capture_native_attempt(world: object, sensors: dict, actor_sampler: object,
                           road: dict, ego_id: int, target_id: int,
                           frame_map: object, attempt: Path, *,
                           frame_count: int = 900, timeout_s: float = 5.0,
                           diagnostic_profile: dict | None = None,
                           before_tick=None) -> dict:
    """Acquire original rows and PNGs; validate joins before returning sources.

    ``actor_sampler(snapshot)`` must read both live actors and return the fields
    required by ``collect_native_trace``. ``before_tick(index)`` applies the
    caller's actor controller. Requested motion is never reported here as
    observed motion. No sensor is destroyed: ownership stays with the caller.
    """
    sizes = PROFILE if diagnostic_profile is None else diagnostic_profile
    if set(sensors) != set(CAMERAS) or set(sizes) != set(CAMERAS):
        raise ValueError('all four original camera sensors/profile required')
    if frame_count < 8 or timeout_s <= 0:
        raise ValueError('valid capture count and callback timeout required')
    settings = world.get_settings()
    if settings.synchronous_mode is not True or abs(settings.fixed_delta_seconds - 0.05) > 1e-9:
        raise ValueError('Native synchronous 20 Hz world required')
    attempt = Path(attempt)
    if not attempt.is_dir() or any((attempt / f'{name}.zip').exists() for name in CAMERAS):
        raise ValueError('fresh attempt directory and camera archives required')
    queues = {name: Queue(maxsize=frame_count + 2) for name in CAMERAS}
    for name in CAMERAS:
        sensors[name].listen(lambda image, name=name: queues[name].put_nowait(image))
    paths = {name: attempt / f'{name}.zip' for name in CAMERAS}
    rows = []
    try:
        with ExitStack() as stack:
            archives = {name: stack.enter_context(ZipFile(path, 'x', compression=ZIP_STORED))
                        for name, path in paths.items()}
            # The per-camera callback queue is independent. A missing or stale
            # callback fails the acquisition instead of shifting frame indices.
            for index in range(frame_count):
                if before_tick is not None:
                    before_tick(index)
                native_id = world.tick()
                snapshot = world.get_snapshot()
                if snapshot.frame != native_id:
                    raise ValueError('world snapshot differs from Native tick')
                row = dict(actor_sampler(snapshot))
                row.update(native_frame_id=native_id,
                           elapsed_seconds=snapshot.timestamp.elapsed_seconds,
                           ego_id=ego_id, target_id=target_id)
                camera_ids = {}
                for name in CAMERAS:
                    try:
                        image = queues[name].get(timeout=timeout_s)
                    except Empty as exc:
                        raise ValueError(name + ' original camera callback missing') from exc
                    if image.frame != native_id:
                        raise ValueError(name + ' original camera callback frame mismatch')
                    camera_ids[name] = image.frame
                    archives[name].writestr(f'{index:06d}.png',
                                             _png_from_native(image, sizes[name]))
                row['camera_frame_ids'] = camera_ids
                rows.append(row)
        trace = collect_native_trace(rows, road, ego_id, target_id, frame_map,
                                     expected_frames=frame_count)
        cameras = {name: {'path': path.name,
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                   for name, path in paths.items()}
        return {'trace': trace, 'cameras': cameras,
                'diagnostic_profile': diagnostic_profile is not None,
                'physical_acceptance_claimed': False}
    except Exception:
        for path in paths.values():
            path.unlink(missing_ok=True)
        raise
