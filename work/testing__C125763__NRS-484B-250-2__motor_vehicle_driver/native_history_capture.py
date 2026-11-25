"""Seal original CARLA body histories for the C125763 entry-time measurement.

The caller owns CARLA actors and world restoration. This module records the
snapshot's original frame/time and bounding-box vertices after each world tick;
it never chooses a legal timing threshold or rewrites a recorded trajectory.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
import sys

from PIL import Image

from native_construction import reviewed_scene

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _bytes(path: Path, content: bytes) -> str:
    if path.exists():
        raise ValueError("Capture destination already exists: " + path.name)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _vertices(actor) -> list[list[float]]:
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) != 8:
        raise ValueError("CARLA body box must have eight world vertices")
    points = [[float(p.x), float(p.y)] for p in vertices]
    if not all(math.isfinite(n) for point in points for n in point):
        raise ValueError("CARLA body box has nonfinite coordinates")
    # The XY projection of a 3D box has duplicate corners. Its convex hull is
    # the measured body footprint, including yaw rather than a center proxy.
    unique = sorted({tuple(point) for point in points})
    if len(unique) < 3:
        raise ValueError("CARLA body footprint is degenerate")
    def turn(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    lower, upper = [], []
    for point in unique:
        while len(lower) >= 2 and turn(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(unique):
        while len(upper) >= 2 and turn(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return [list(point) for point in lower[:-1] + upper[:-1]]


def capture(world, packet_path: Path, ego, other, output: Path, frame_count: int = 900,
            *, camera_readers=None, camera_dimensions=None, before_tick=None) -> dict:
    """Capture one 20 Hz synchronous run; output directory must be new and empty.

    The reviewed packet binds the live map and source bytes. An independent
    timing pass must still check the sealed histories and source hashes.
    """
    if type(frame_count) is not int or frame_count < 2:
        raise ValueError("Capture requires at least two original frames")
    scene = reviewed_scene(packet_path, world)
    bounds = scene.get("intersection_bounds_xy_m")
    if (not isinstance(bounds, list) or len(bounds) != 4 or
            not all(type(v) in (int, float) and math.isfinite(v) for v in bounds) or
            bounds[0] >= bounds[2] or bounds[1] >= bounds[3]):
        raise ValueError("Reviewed intersection footprint bounds are absent")
    if ego.id == other.id:
        raise ValueError("The two original actors must differ")
    settings = world.get_settings()
    if not settings.synchronous_mode or abs(settings.fixed_delta_seconds - .05) > 1e-9:
        raise ValueError("World must already be synchronous at exactly 20 Hz")
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Capture destination must be a new empty directory")
    output.mkdir(parents=True, exist_ok=True)
    if camera_readers is not None:
        if (not isinstance(camera_readers, dict) or set(camera_readers) != set(CAMERAS)
                or not all(callable(camera_readers[name]) for name in CAMERAS)):
            raise ValueError('four original camera readers required')
        if not isinstance(camera_dimensions, dict) or set(camera_dimensions) != set(CAMERAS):
            raise ValueError('four original camera dimensions required')
        media_root = output / 'original-frames'
        media_root.mkdir()
    histories = {"ego": [], "other": []}
    camera_rows = []
    previous = None
    if before_tick is not None and not callable(before_tick):
        raise ValueError('before_tick must be callable')
    runtime_path = str(Path(__file__).resolve().parents[2] / 'runtime/scenario_pipeline')
    if runtime_path not in sys.path:
        sys.path.insert(0, runtime_path)
    from worker_exchange.native_output import FrameMap
    with FrameMap(output / 'video_frames.jsonl') as frame_map:
        for index in range(frame_count):
            if before_tick is not None:
                before_tick(index)
            tick_frame = world.tick()
            snapshot = world.get_snapshot()
            frame = snapshot.frame
            time_s = float(snapshot.timestamp.elapsed_seconds)
            if type(frame) is not int or frame != tick_frame or not math.isfinite(time_s):
                raise ValueError("World tick and snapshot identity differ")
            if previous is not None and (frame != previous[0] + 1 or
                                         not .049 <= time_s - previous[1] <= .051):
                raise ValueError("World did not preserve a contiguous 20 Hz original clock")
            previous = frame, time_s
            frame_map.append(frame, time_s)
            if camera_readers is not None:
                views = {}
                for name in CAMERAS:
                    image = camera_readers[name](frame)
                    if (not isinstance(image, dict) or image.get('frame') != frame or
                            not isinstance(image.get('png_bytes'), bytes)):
                        raise ValueError('original camera frame identity or pixels missing')
                    content = image['png_bytes']
                    try:
                        with Image.open(io.BytesIO(content)) as decoded:
                            decoded.load()
                            if (decoded.format != 'PNG' or decoded.size != tuple(camera_dimensions[name])
                                    or decoded.mode not in ('RGB', 'RGBA')):
                                raise ValueError('original camera PNG profile differs')
                    except (OSError, TypeError) as error:
                        raise ValueError('original camera PNG decode failed') from error
                    path = media_root / f'{name}-{len(camera_rows):06d}.png'
                    views[name] = {'path': str(path.relative_to(output)),
                                   'sha256': _bytes(path, content)}
                camera_rows.append({'frame': frame, 'time_s': time_s, 'views': views})
            for name, actor in (("ego", ego), ("other", other)):
                histories[name].append({"frame": frame, "time_s": time_s,
                                        "actor_id": actor.id,
                                        "body_vertices_xy_m": _vertices(actor)})
    site = dict(scene)
    site.update({"ego_actor_id": ego.id, "other_actor_id": other.id})
    manifest = {}
    files = {"site-context.json": (json.dumps(site, sort_keys=True) + "\n").encode(),
             "road.xodr": world.get_map().to_opendrive().encode()}
    for name, rows in histories.items():
        files[name + "-body-history.jsonl"] = "".join(
            json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()
    if camera_readers is not None:
        files['camera-frame-map.jsonl'] = ''.join(
            json.dumps(row, sort_keys=True) + '\n' for row in camera_rows).encode()
    for name, content in files.items():
        manifest[name] = {"kind": "original_native", "sha256": _bytes(output / name, content)}
    manifest['video_frames.jsonl'] = {
        "kind": "original_native", "sha256": hashlib.sha256(
            (output / 'video_frames.jsonl').read_bytes()).hexdigest()}
    _bytes(output / "source-manifest.json", (json.dumps(manifest, sort_keys=True) + "\n").encode())
    return {"frame_count": frame_count, "first_frame": histories["ego"][0]["frame"],
            "last_frame": histories["ego"][-1]["frame"], "source_manifest": manifest,
            "camera_view_frames": len(camera_rows) * len(CAMERAS)}


def audit_media(attempt, *, camera_dimensions):
    """Reopen every camera PNG and join its original clock to both bodies."""
    root = Path(attempt)
    manifest = json.loads((root / 'source-manifest.json').read_text(encoding='utf-8'))
    if set(camera_dimensions) != set(CAMERAS):
        raise ValueError('four original camera dimensions required')
    sources = {}
    for name in ('ego-body-history.jsonl', 'other-body-history.jsonl',
                 'camera-frame-map.jsonl', 'video_frames.jsonl'):
        binding = manifest.get(name)
        if not isinstance(binding, dict) or binding.get('kind') != 'original_native':
            raise ValueError('original camera/body source missing')
        source_path = root / name
        if source_path.is_symlink() or not source_path.is_file():
            raise ValueError('original camera/body source is not a retained file')
        data = source_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != binding.get('sha256'):
            raise ValueError('original camera/body source changed')
        sources[name] = [json.loads(line) for line in data.decode('utf-8').splitlines()]
    ego, other, cameras, mapping = (sources[name] for name in
                           ('ego-body-history.jsonl', 'other-body-history.jsonl',
                            'camera-frame-map.jsonl', 'video_frames.jsonl'))
    if not ego or len(ego) != len(other) or len(ego) != len(cameras) or len(ego) != len(mapping):
        raise ValueError('original camera/body frame count differs')
    for index, (a, b, row) in enumerate(zip(ego, other, cameras)):
        if (a['frame'], a['time_s']) != (b['frame'], b['time_s']) or (
                row.get('frame'), row.get('time_s')) != (a['frame'], a['time_s']):
            raise ValueError('original camera/body clock differs')
        if mapping[index] != {'video_frame': index, 'carla_frame': a['frame'],
                              'native_frame': a['frame'], 'time_s': a['time_s']}:
            raise ValueError('canonical original video frame map differs')
        if not isinstance(row.get('views'), dict) or set(row['views']) != set(CAMERAS):
            raise ValueError('four original camera views required')
        for name in CAMERAS:
            ref = row['views'][name]
            expected = f'original-frames/{name}-{index:06d}.png'
            if ref.get('path') != expected:
                raise ValueError('original camera frame path differs')
            image_path = root / expected
            if image_path.is_symlink() or not image_path.is_file():
                raise ValueError('original camera frame is not a retained file')
            content = image_path.read_bytes()
            if hashlib.sha256(content).hexdigest() != ref.get('sha256'):
                raise ValueError('original camera frame bytes changed')
            with Image.open(io.BytesIO(content)) as image:
                image.load()
                if image.format != 'PNG' or image.size != tuple(camera_dimensions[name]):
                    raise ValueError('original camera frame decode/profile differs')
    return {'joined_original_frames': len(ego), 'decoded_camera_frames': len(ego) * len(CAMERAS),
            'physical_acceptance': False, 'legal_verdict_claimed': False}
