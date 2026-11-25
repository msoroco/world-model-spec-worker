"""Independent full decode of saved camera media; observations only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


class MediaError(ValueError):
    pass


def decode_view(root, source_ref, expected_frames, expected_width, expected_height):
    base = Path(root).resolve()
    path = (base / source_ref['path']).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise MediaError('missing or escaping camera source')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != source_ref['sha256']:
        raise MediaError('camera source hash mismatch')
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
         '-count_frames', '-show_entries',
         'stream=width,height,r_frame_rate,nb_read_frames',
         '-of', 'json', str(path)], capture_output=True, text=True, check=False)
    if probe.returncode:
        raise MediaError('ffprobe rejected camera source: ' + probe.stderr.strip()[:200])
    streams = json.loads(probe.stdout).get('streams', [])
    if len(streams) != 1:
        raise MediaError('camera video stream missing')
    stream = streams[0]
    if (stream.get('width'), stream.get('height')) != (expected_width, expected_height):
        raise MediaError('camera dimensions mismatch')
    if stream.get('r_frame_rate') != '20/1':
        raise MediaError('camera frame rate mismatch')
    if int(stream.get('nb_read_frames', -1)) != expected_frames:
        raise MediaError('camera frame count mismatch')
    decode = subprocess.run(
        ['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-map', '0:v:0',
         '-f', 'null', '-'], capture_output=True, text=True, check=False)
    if decode.returncode:
        raise MediaError('full camera decode failed: ' + decode.stderr.strip()[:200])
    return {'path': source_ref['path'], 'sha256': digest,
            'decoded_frames': expected_frames, 'fps': 20,
            'width': expected_width, 'height': expected_height,
            'full_decode_exit_code': 0, 'physical_visibility': 'unreviewed'}


def audit_four_views(root, views, expected_frames):
    names = ('overview', 'approach', 'reference_corner', 'driver_reference')
    if set(views) != set(names):
        raise MediaError('four-view capture missing')
    paths = [views[name]['source']['path'] for name in names]
    if len(set(paths)) != len(paths):
        raise MediaError('four-view sources must be distinct')
    result = {}
    for name in names:
        item = views[name]
        result[name] = decode_view(root, item['source'], expected_frames,
                                   item['width'], item['height'])
    return result


def audit_manifest(root, manifest_ref, output_path):
    """Decode every sealed camera in a saved attempt and write a source receipt."""
    base = Path(root).resolve()
    manifest_path = (base / manifest_ref['path']).resolve()
    if not manifest_path.is_relative_to(base) or not manifest_path.is_file():
        raise MediaError('missing or escaping media manifest')
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if digest != manifest_ref['sha256']:
        raise MediaError('media manifest hash mismatch')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    count = manifest.get('duration_frames')
    if not isinstance(count, int) or count != 900 or manifest.get('fps') != 20:
        raise MediaError('45 second 20 Hz capture missing')
    if not manifest.get('case_id'):
        raise MediaError('case identity missing')
    views = audit_four_views(base, manifest.get('camera_views', {}), count)
    receipt = {'case_id': manifest['case_id'], 'manifest_ref': manifest_ref,
               'camera_views': views, 'physical_visibility': 'unreviewed',
               'legal_verdict': None}
    output = Path(output_path).resolve()
    if output.parent != base:
        raise MediaError('receipt must stay in saved attempt root')
    output.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit_manifest(args.root, {'path': args.manifest, 'sha256': args.manifest_sha256}, args.output)
