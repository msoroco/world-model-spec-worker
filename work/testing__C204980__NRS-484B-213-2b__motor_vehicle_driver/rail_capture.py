"""Acquire six exact railroad cases at 20 Hz from a reviewed Native adapter.

The adapter owns the CARLA world, actors and cameras. Original site records are
checked against the live map before begin or spawn. Outputs are immutable source
packets for saved processing; this module makes no physical/legal acceptance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rail_left import CASES, construct, measure_original
from reviewed_rail import SOURCE_KINDS, load_reviewed_scene


ASSIGNMENT = 'testing__C204980__NRS-484B-213-2b__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _write_new(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, sort_keys=True) + '\n')


def capture(adapter, packet_path: Path, source_root: Path, output: Path,
            case_id: str, *, frames: int = 900):
    cases = {ASSIGNMENT + '__' + item.case_id: item for item in CASES}
    if case_id not in cases or frames != 900:
        raise ValueError('exact 900-frame railroad case required')
    output = Path(output)
    if not output.is_dir() or any(output.iterdir()):
        raise ValueError('fresh empty original capture directory required')
    owned = None
    try:
        # This readback must precede every Native mutation.
        scene = load_reviewed_scene(packet_path, source_root,
                                    adapter.live_opendrive(), case_id)
        adapter.begin(scene, case_id)
        owned = construct(adapter, scene, cases[case_id])
        original_rows = []
        camera_frames = {camera: [] for camera in CAMERAS}
        last_frame = None
        for _ in range(frames):
            frame = adapter.tick()
            if type(frame) is not int or (last_frame is not None and frame != last_frame + 1):
                raise ValueError('original Native frame gap')
            last_frame = frame
            row = adapter.sample_original(frame, scene)
            if not isinstance(row, dict) or row.get('original_frame') != frame:
                raise ValueError('original rail source row/frame mismatch')
            images = adapter.camera_frames(frame)
            if not isinstance(images, dict) or set(images) != set(CAMERAS) or any(
                    images[camera] != frame for camera in CAMERAS):
                raise ValueError('four original camera frame join missing')
            original_rows.append(row)
            for camera in CAMERAS:
                camera_frames[camera].append(frame)
        observation = measure_original(original_rows, scene, cases[case_id])
        for camera in CAMERAS:
            adapter.write_camera_video(camera, output / (camera + '.mkv'))
            if not (output / (camera + '.mkv')).is_file() or not (output / (camera + '.mkv')).stat().st_size:
                raise ValueError('original camera video missing: ' + camera)
        (output / 'rail-frames.jsonl').write_text(''.join(
            json.dumps(row, sort_keys=True) + '\n' for row in original_rows), encoding='utf-8')
        _write_new(output / 'frame-map.json', {
            'frames': [row['original_frame'] for row in original_rows],
            'camera_frames': camera_frames})
        _write_new(output / 'rail-context.json', {
            'case_id': case_id,
            'scene': scene,
            'reviewed_map_sha256': scene['map_opendrive_sha256'],
            'physical_acceptance_claimed': False})
        for kind in SOURCE_KINDS:
            source = json.loads(Path(packet_path).read_text())['sources'][kind]
            path = output / ('reviewed-' + kind + '.json')
            if path.exists() or path.is_symlink():
                raise ValueError('reviewed source output already exists')
            path.write_bytes((Path(source_root) / source['path']).read_bytes())
            if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
                raise ValueError('reviewed source changed during capture')
        source_files = ('rail-frames.jsonl', 'frame-map.json', 'rail-context.json',
                        *(camera + '.mkv' for camera in CAMERAS),
                        *(f'reviewed-{kind}.json' for kind in SOURCE_KINDS))
        hashes = {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                  for name in source_files}
        _write_new(output / 'source-hashes.json', hashes)
        return {'case_id': case_id, 'frame_count': 900, 'source_sha256': hashes,
                'diagnostic_probe': observation,
                'physical_acceptance_claimed': False}
    finally:
        adapter.close(owned['owned'] if owned else ())
