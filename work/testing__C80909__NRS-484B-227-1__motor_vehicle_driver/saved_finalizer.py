"""Saved C80909 divider observations from original Native and camera sources."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from divider_measurements import analyze
from native_capture import CAMERAS
from shapely.geometry import Polygon


def _video_info(path):
    probe = subprocess.run([
        'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=codec_name,width,height,r_frame_rate,nb_read_frames',
        '-of', 'json', str(path)], capture_output=True, text=True)
    if probe.returncode:
        raise ValueError('Original camera frame probe failed: ' + path.name)
    streams = json.loads(probe.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError('One original camera video stream required: ' + path.name)
    decode = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path),
                             '-an', '-f', 'null', '-'], capture_output=True, text=True)
    if decode.returncode or decode.stderr.strip():
        raise ValueError('Full original camera decode failed: ' + path.name)
    return streams[0]


def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def finalize(root, *, probe=_video_info):
    root = Path(root)
    observations = analyze(root)
    context = json.loads((root / 'divider_context.json').read_text())
    site_path = root / 'site_source_receipt.json'
    barrier_path = root / 'barrier_receipt.json'
    if not site_path.is_file() or not barrier_path.is_file():
        raise ValueError('Missing original site or barrier source receipt')
    site = json.loads(site_path.read_text())
    barrier = json.loads(barrier_path.read_text())
    if site.get('native_map_name') != context['native_map_id'] or not site.get('source_refs'):
        raise ValueError('Original site source binding differs')
    for ref in site['source_refs']:
        source = (root / ref['path']).resolve()
        if not source.is_relative_to(root.resolve()) or not source.is_file() or _sha256(source) != ref['sha256']:
            raise ValueError('Original site source missing or changed')
    opening = Polygon(context['opening_xy_m'])
    if not Polygon(barrier.get('opening_xy_m', [])).equals(opening):
        raise ValueError('Original barrier opening differs')
    sections = barrier.get('barrier_footprints_xy_m', [])
    offsets = barrier.get('section_axis_offsets_m', [])
    if (len(sections) != 2 or len(offsets) != 2 or offsets[0] * offsets[1] >= 0 or
            any(Polygon(section).intersects(opening) for section in sections)):
        raise ValueError('Original barrier sections do not straddle clear opening')
    observations['site_context_sources'] = {
        'native_map_name': site['native_map_name'],
        'source_refs': site['source_refs'],
        'site_source_sha256': _sha256(site_path),
        'barrier_source_sha256': _sha256(barrier_path)}
    count = len(observations['samples'])
    if count < 4:
        raise ValueError('Incomplete Native movement history')
    sources = {}
    for name, (width, height) in CAMERAS.items():
        path = root / (name + '.mkv')
        if not path.is_file():
            raise ValueError('Missing original source camera: ' + name)
        info = probe(path)
        if (info.get('codec_name') != 'ffv1' or
                (info.get('width'), info.get('height')) != (width, height) or
                info.get('r_frame_rate') != '20/1' or
                str(info.get('nb_read_frames')) != str(count)):
            raise ValueError('Original camera profile or frame count differs: ' + name)
        sources[name] = {'path': path.name,
                         'sha256': _sha256(path),
                         'decoded_frames': count, 'width': width, 'height': height}
    observations['camera_sources'] = sources
    observations['measurement_contract'] = {
        'case_id': 'testing__C80909__NRS-484B-227-1__motor_vehicle_driver__left_through_opening',
        'complete_body_crossing': 'source geometry, not legal verdict',
        'heading_change': 'signed original Native yaw difference',
        'public_authority_establishment': 'requires independent original source review',
        'physical_completion': 'requires independent original camera review'}
    observations['physical_acceptance_claimed'] = False
    return observations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Fresh saved observation path required')
    result = finalize(args.capture)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
