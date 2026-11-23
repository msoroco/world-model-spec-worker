"""Encode original four-camera BGRA frames after Native capture, without inventing pixels."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess

from native_camera import VIEWS


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _private(path: Path) -> Path:
    path = Path(path).resolve()
    source = Path(__file__).resolve()
    private = next((part for part in source.parents if part.name == '.runtime-work'),
                   source.parents[2] / '.runtime-work')
    if path != private and private not in path.parents:
        raise ValueError('camera media must stay under .runtime-work')
    return path


def _trace_rows(trace: Path, raw_root: Path) -> tuple[list, dict]:
    rows = [json.loads(line) for line in trace.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('original Native trace is empty')
    case_id = rows[0].get('case_id')
    source_hash = rows[0].get('source_packet_sha256')
    seen = set()
    frames = []
    files = {name: [] for name, _, _ in VIEWS}
    for index, row in enumerate(rows):
        native = row.get('native_frame')
        if (row.get('case_id') != case_id or row.get('source_packet_sha256') != source_hash or
                row.get('original_sample_claim') is not True or not isinstance(native, dict) or
                native.get('origin') != 'native_world_snapshot'):
            raise ValueError('original trace case/source identity differs')
        frame = native.get('frame')
        time_s = native.get('time_s')
        if (type(frame) is not int or frame in seen or
                (index and frame != frames[-1]['carla_frame'] + 1) or
                type(time_s) not in (int, float) or not math.isfinite(time_s) or
                abs(row.get('time_s', -1) - time_s) > 1e-6 or
                (index and time_s <= frames[-1]['time_s'])):
            raise ValueError('original trace frame/time sequence differs')
        cameras = native.get('original_cameras')
        if not isinstance(cameras, dict) or set(cameras) != {name for name, _, _ in VIEWS}:
            raise ValueError('original four-camera frame missing')
        for name, width, height in VIEWS:
            item = cameras[name]
            relative = item.get('raw_bgra')
            if (item.get('view') != name or item.get('frame') != frame or
                    item.get('width') != width or item.get('height') != height or
                    item.get('source_packet_sha256') != source_hash or
                    abs(item.get('time_s', -1) - time_s) > .05 or
                    not isinstance(relative, str)):
                raise ValueError('original camera/Native frame binding differs')
            raw = (raw_root / relative).resolve()
            if raw_root not in raw.parents or not raw.is_file() or raw.stat().st_size != width * height * 4:
                raise ValueError('original camera pixel source missing')
            if sha(raw) != item.get('sha256'):
                raise ValueError('original camera pixel hash differs')
            files[name].append(raw)
        frames.append({'video_frame': index, 'carla_frame': frame, 'time_s': time_s})
        seen.add(frame)
    return frames, files


def _encode(files: list[Path], width: int, height: int, destination: Path) -> None:
    command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
               '-f', 'rawvideo', '-pixel_format', 'bgra', '-video_size', f'{width}x{height}',
               '-framerate', '20', '-i', 'pipe:0', '-frames:v', str(len(files)),
               '-an', '-c:v', 'ffv1', '-level', '3', '-pix_fmt', 'bgra', str(destination)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE)
    try:
        for path in files:
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    process.stdin.write(chunk)
        process.stdin.close()
        error = process.stderr.read()
        if process.wait(timeout=300) != 0:
            raise ValueError('lossless camera encode failed: ' + error.decode('utf-8', 'replace')[-1000:])
    except Exception:
        process.kill()
        process.wait()
        destination.unlink(missing_ok=True)
        raise
    finally:
        process.stderr.close()
    if not destination.is_file() or destination.stat().st_size == 0:
        raise ValueError('lossless camera output missing')


def finalize(trace_path: Path, raw_root: Path, output_root: Path) -> dict:
    trace_path, raw_root, output_root = map(_private, (trace_path, raw_root, output_root))
    targets = [output_root / (name + '.mkv') for name, _, _ in VIEWS]
    targets += [output_root / 'video_frames.jsonl', output_root / 'media-receipt.json']
    if any(path.exists() for path in targets):
        raise ValueError('retain previous camera media')
    frames, files = _trace_rows(trace_path, raw_root)
    output_root.mkdir(parents=True, exist_ok=True)
    videos = {}
    for name, width, height in VIEWS:
        destination = output_root / (name + '.mkv')
        _encode(files[name], width, height, destination)
        videos[name] = sha(destination)
    mapping = output_root / 'video_frames.jsonl'
    with mapping.open('x') as stream:
        for item in frames:
            stream.write(json.dumps(item, sort_keys=True) + '\n')
    receipt = {'format': 'c153046-original-four-camera-media',
               'case_id': json.loads(trace_path.read_text().splitlines()[0])['case_id'],
               'trace_sha256': sha(trace_path), 'frame_map_sha256': sha(mapping),
               'video_sha256': videos, 'frames': len(frames),
               'source_packet_sha256': json.loads(trace_path.read_text().splitlines()[0])['source_packet_sha256'],
               'physical_acceptance_claimed': False, 'pixel_visibility_verified': False}
    (output_root / 'media-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt
