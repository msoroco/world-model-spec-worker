"""Independent saved-source integrity check for the four exact departure cases.

This checks original trace/map/camera bindings and decodes source PNG frames
when bound. It does not claim physical visibility or make a legal judgment.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('departure_saved_geometry', HERE / 'departure_geometry.py')
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)
pixel_spec = importlib.util.spec_from_file_location('departure_saved_pixels', HERE / 'saved_pixels.py')
pixels = importlib.util.module_from_spec(pixel_spec)
pixel_spec.loader.exec_module(pixels)
ASSIGNMENT = 'testing__C109705__NRS-484B-400-2b__motor_vehicle_driver'
SUFFIXES = ('near_centerline', 'farther_from_centerline',
            'imaginary_near_centerline', 'imaginary_farther_from_centerline')
CAMERAS = ('dash', 'front', 'left', 'right')


def _read_source(root, binding, label):
    if not isinstance(binding, dict) or not isinstance(binding.get('path'), str) or not isinstance(binding.get('sha256'), str):
        raise ValueError(f'{label} source binding missing')
    path = Path(binding['path'])
    if path.is_absolute() or not path.parts or any(part in ('.', '..') for part in path.parts):
        raise ValueError(f'{label} path escapes attempt')
    if any((root / Path(*path.parts[:index])).is_symlink()
           for index in range(1, len(path.parts) + 1)):
        raise ValueError(f'{label} source path is symlinked')
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError(f'{label} source file missing')
    if hashlib.sha256(resolved.read_bytes()).hexdigest() != binding['sha256']:
        raise ValueError(f'{label} source hash differs')
    return resolved


def _load_json(root, binding, label):
    try:
        return json.loads(_read_source(root, binding, label).read_text(encoding='utf-8'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'{label} source JSON invalid') from exc


def audit(attempt_dir, manifest, *, case_id, allow_diagnostic=False):
    """Verify original 45 s / 20 Hz sources and compute saved departure bounds.

    Manifest is an attempt-local binding to source-hashed map, trace and camera
    index packets. A diagnostic flag is explicit and still never proves pixels.
    """
    root = Path(attempt_dir).resolve()
    if case_id not in {ASSIGNMENT + '__' + suffix for suffix in SUFFIXES}:
        raise ValueError('case differs from exact assignment')
    if not isinstance(manifest, dict) or manifest.get('case_id') != case_id:
        raise ValueError('saved attempt case identity differs')
    if manifest.get('acquisition_kind') != 'original_native' and not allow_diagnostic:
        raise ValueError('original Native acquisition required for delivery')
    if manifest.get('rate_hz') != 20 or manifest.get('duration_s') != 45:
        raise ValueError('saved duration or sample rate differs')
    map_packet = _load_json(root, manifest.get('map'), 'map')
    trace = _load_json(root, manifest.get('trace'), 'trace')
    index = _load_json(root, manifest.get('camera_index'), 'camera index')
    if map_packet.get('source_sha256') is None or not map_packet.get('source_sha256'):
        raise ValueError('reviewed map source hash missing')
    _read_source(root, {'path': map_packet.get('source_path'),
                        'sha256': map_packet['source_sha256']}, 'original map')
    expected_kind = ('source_derived_imaginary' if case_id.split('__')[-1].startswith('imaginary_')
                     else 'mapped')
    if map_packet.get('centerline_kind') != expected_kind:
        raise ValueError('departure centerline convention differs')
    measurement = geometry.measure(map_packet, trace, case_id=case_id)
    rows = trace.get('samples')
    if len(rows) != 900 or any(row.get('frame') != rows[0].get('frame') + i for i, row in enumerate(rows)):
        raise ValueError('900 consecutive original trace frames required')
    times = [row.get('elapsed_seconds') for row in rows]
    if any(type(t) not in (int, float) or not math.isfinite(t) for t in times):
        raise ValueError('original elapsed clock missing or invalid')
    if any(abs(t - times[0] - i / 20) > 0.002 for i, t in enumerate(times)):
        raise ValueError('saved original 20 Hz clock drift')
    if index.get('case_id') != case_id or set(index.get('channels', {})) != set(CAMERAS):
        raise ValueError('four original camera channels differ')
    frames = [row['frame'] for row in rows]
    source_files = set()
    channel_paths = {}
    for channel in CAMERAS:
        camera_rows = index['channels'][channel]
        if not isinstance(camera_rows, list) or len(camera_rows) != 900:
            raise ValueError('900 original camera frame references required')
        for frame, camera_row in zip(frames, camera_rows):
            if not isinstance(camera_row, dict) or camera_row.get('frame') != frame or camera_row.get('channel') != channel:
                raise ValueError('original camera frame identity differs')
            path, sha = camera_row.get('source_path'), camera_row.get('source_sha256')
            if path in channel_paths and channel_paths[path] != channel:
                raise ValueError('original camera sources alias across channels')
            channel_paths[path] = channel
            if (path, sha) not in source_files:
                _read_source(root, {'path': path, 'sha256': sha}, 'original camera')
                source_files.add((path, sha))
    decoded = None
    if manifest.get('camera_media_kind') == 'original_png_frames':
        decoded = pixels.decode(root, index, frames,
                                delivery=manifest.get('acquisition_kind') == 'original_native')
    elif manifest.get('acquisition_kind') == 'original_native':
        raise ValueError('original Native delivery requires full PNG frame decode')
    return {'case_id': case_id, 'source_integrity': 'passed',
            'original_frames': 900, 'rate_hz': 20, 'duration_s': 45,
            'observed_span_s': times[-1] - times[0],
            'original_camera_channels': list(CAMERAS), 'source_file_count': len(source_files),
            'departure_measurement': measurement, 'full_video_decode': False,
            'full_source_decode': bool(decoded), 'pixel_decode': decoded,
            'actual_pixels': bool(decoded), 'physical_completion': False,
            'statutory_position_judgment': None,
            'limitations': (['Original PNG pixels decoded; participant visibility remains unverified.']
                            if decoded else ['This diagnostic verifies indexed source bytes, not decoded pixels.'])
                           + ['Native motion and camera visibility require local physical review.']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.attempt, json.loads(Path(args.manifest).read_text(encoding='utf-8')),
                   case_id=args.case, allow_diagnostic=args.allow_diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
