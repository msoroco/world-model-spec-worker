"""Seal original CARLA bodies and four cameras for the C125745 precedence pair.

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


def _retained_file(root: Path, relative: str) -> Path:
    """Require each original source path component to belong to the attempt."""
    root = Path(root)
    parts = Path(relative).parts
    if (root.is_symlink() or not root.is_dir() or not parts or
            Path(relative).is_absolute() or '..' in parts):
        raise ValueError('original source is not a retained file')
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('original source is not a retained file')
    if not path.is_file() or root.resolve() not in path.resolve().parents:
        raise ValueError('original source is not a retained file')
    return path


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
            *, camera_readers=None, camera_dimensions=None, before_tick=None,
            diagnostic=False, case_id=None) -> dict:
    """Capture one 20 Hz synchronous run; output directory must be new and empty.

    The reviewed packet binds the live map and source bytes. An independent
    timing pass must still check the sealed histories and source hashes.
    """
    if type(frame_count) is not int or frame_count < 2:
        raise ValueError("Capture requires at least two original frames")
    scene = reviewed_scene(packet_path, world, diagnostic=diagnostic)
    if case_id not in ('precedence', 'advance'):
        raise ValueError('one exact precedence case ID required')
    if not diagnostic and frame_count != 900:
        raise ValueError("original capture requires exactly 900 frames")
    if ego.id == other.id:
        raise ValueError("The two original actors must differ")
    settings = world.get_settings()
    if not settings.synchronous_mode or abs(settings.fixed_delta_seconds - .05) > 1e-9:
        raise ValueError("World must already be synchronous at exactly 20 Hz")
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Capture destination must be a new empty directory")
    output.mkdir(parents=True, exist_ok=True)
    if (not isinstance(camera_readers, dict) or set(camera_readers) != set(CAMERAS)
            or not all(callable(camera_readers[name]) for name in CAMERAS)):
        raise ValueError('four original camera readers required')
    if not isinstance(camera_dimensions, dict) or set(camera_dimensions) != set(CAMERAS):
        raise ValueError('four original camera dimensions required')
    if not diagnostic and camera_dimensions != {
            'overview': [1920, 1080], 'approach': [1280, 720],
            'reference_corner': [1280, 720], 'driver_reference': [1280, 720]}:
        raise ValueError('original camera profile differs')
    media_root = output / 'original-frames'
    media_root.mkdir()
    histories = {"ego": [], "other": []}
    trace = []
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
            transform = ego.get_transform()
            velocity = ego.get_velocity()
            position = transform.location
            components = (position.x, position.y, position.z, transform.rotation.yaw,
                          velocity.x, velocity.y, velocity.z)
            if any(not math.isfinite(float(value)) for value in components):
                raise ValueError('original ego trace has nonfinite pose or speed')
            trace.append({'frame': frame, 'time_s': time_s,
                          'position': {'x': float(position.x), 'y': float(position.y),
                                       'z': float(position.z)},
                          'heading_deg': float(transform.rotation.yaw),
                          'speed_mps': math.sqrt(float(velocity.x) ** 2 +
                                                 float(velocity.y) ** 2 +
                                                 float(velocity.z) ** 2)})
    site = dict(scene)
    site.update({"ego_actor_id": ego.id, "other_actor_id": other.id,
                 "case_id": scene['assignment_id'] + '__' + case_id})
    manifest = {}
    files = {"site-context.json": (json.dumps(site, sort_keys=True) + "\n").encode(),
             "road.xodr": world.get_map().to_opendrive().encode()}
    for source_name, retained_name in (
            ('device_source', 'original-device-source.txt'),
            ('highway_source', 'original-highway-source.txt')):
        original = Path(packet_path).parent / scene[source_name]['path']
        content = original.read_bytes()
        if hashlib.sha256(content).hexdigest() != scene[source_name]['sha256']:
            raise ValueError('reviewed original source changed during capture: ' + source_name)
        files[retained_name] = content
    for name, rows in histories.items():
        files[name + "-body-history.jsonl"] = "".join(
            json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()
    files['trace.jsonl'] = ''.join(json.dumps(row, sort_keys=True) + '\n'
                                   for row in trace).encode()
    if camera_readers is not None:
        files['camera-frame-map.jsonl'] = ''.join(
            json.dumps(row, sort_keys=True) + '\n' for row in camera_rows).encode()
    for name, content in files.items():
        manifest[name] = {"kind": "original_native", "sha256": _bytes(output / name, content)}
    manifest['video_frames.jsonl'] = {
        "kind": "original_native", "sha256": hashlib.sha256(
            (output / 'video_frames.jsonl').read_bytes()).hexdigest()}
    manifest_bytes = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    _bytes(output / "source-manifest.json", manifest_bytes)
    # The pinned saved-processing staging skips source-* receipt names. Keep a
    # byte-identical sealed alias so recorded-only analysis can reopen it.
    _bytes(output / "original-source-manifest.json", manifest_bytes)
    return {"frame_count": frame_count, "first_frame": histories["ego"][0]["frame"],
            "last_frame": histories["ego"][-1]["frame"], "source_manifest": manifest,
            "camera_view_frames": len(camera_rows) * len(CAMERAS)}


def audit_media(attempt, *, camera_dimensions):
    """Reopen every camera PNG and join its original clock to both bodies."""
    root = Path(attempt)
    manifest = json.loads(_retained_file(root, 'source-manifest.json').read_text(
        encoding='utf-8'))
    if set(camera_dimensions) != set(CAMERAS):
        raise ValueError('four original camera dimensions required')
    sources = {}
    for name in ('ego-body-history.jsonl', 'other-body-history.jsonl',
                 'trace.jsonl', 'camera-frame-map.jsonl', 'video_frames.jsonl'):
        binding = manifest.get(name)
        if not isinstance(binding, dict) or binding.get('kind') != 'original_native':
            raise ValueError('original camera/body source missing')
        source_path = _retained_file(root, name)
        data = source_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != binding.get('sha256'):
            raise ValueError('original camera/body source changed')
        sources[name] = [json.loads(line) for line in data.decode('utf-8').splitlines()]
    ego, other, trace, cameras, mapping = (sources[name] for name in
                           ('ego-body-history.jsonl', 'other-body-history.jsonl',
                            'trace.jsonl', 'camera-frame-map.jsonl', 'video_frames.jsonl'))
    if not ego or any(len(ego) != len(rows) for rows in (other, trace, cameras, mapping)):
        raise ValueError('original camera/body frame count differs')
    for index, (a, b, row) in enumerate(zip(ego, other, cameras)):
        if (a['frame'], a['time_s']) != (b['frame'], b['time_s']) or (
                row.get('frame'), row.get('time_s')) != (a['frame'], a['time_s']):
            raise ValueError('original camera/body clock differs')
        if mapping[index] != {'video_frame': index, 'carla_frame': a['frame'],
                              'native_frame': a['frame'], 'time_s': a['time_s']}:
            raise ValueError('canonical original video frame map differs')
        if (trace[index].get('frame'), trace[index].get('time_s')) != (a['frame'], a['time_s']):
            raise ValueError('original ego trace/body clock differs')
        pose = trace[index].get('position', {})
        vertices = a.get('body_vertices_xy_m', [])
        if (not isinstance(pose, dict) or not vertices or
                any(type(pose.get(axis)) not in (int, float) or
                    not math.isfinite(pose[axis]) for axis in ('x', 'y')) or
                not min(point[0] for point in vertices) <= pose['x'] <=
                    max(point[0] for point in vertices) or
                not min(point[1] for point in vertices) <= pose['y'] <=
                    max(point[1] for point in vertices)):
            raise ValueError('original ego trace/body position differs')
        if not isinstance(row.get('views'), dict) or set(row['views']) != set(CAMERAS):
            raise ValueError('four original camera views required')
        for name in CAMERAS:
            ref = row['views'][name]
            expected = f'original-frames/{name}-{index:06d}.png'
            if ref.get('path') != expected:
                raise ValueError('original camera frame path differs')
            image_path = _retained_file(root, expected)
            content = image_path.read_bytes()
            if hashlib.sha256(content).hexdigest() != ref.get('sha256'):
                raise ValueError('original camera frame bytes changed')
            with Image.open(io.BytesIO(content)) as image:
                image.load()
                if image.format != 'PNG' or image.size != tuple(camera_dimensions[name]):
                    raise ValueError('original camera frame decode/profile differs')
    return {'joined_original_frames': len(ego), 'decoded_camera_frames': len(ego) * len(CAMERAS),
            'physical_acceptance': False, 'legal_verdict_claimed': False}
