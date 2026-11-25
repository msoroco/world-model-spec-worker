"""Exact Native bicycle encounter entrypoint for one selected case bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from bicycle_encounter import ASSIGNMENT, CASE_VARIANTS, read_source, verify_site
from native_capture import run as capture_native
from original_source_index import build as build_index


ROOT = Path(__file__).resolve().parent
CASES = {ASSIGNMENT + '__' + suffix for suffix in CASE_VARIANTS}
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(root=ROOT):
    config = json.loads((Path(root) / 'config.json').read_text(encoding='utf-8'))
    if (config.get('assignment_id'), config.get('law_id'),
            config.get('cell_id'), config.get('actor')) != (
            ASSIGNMENT, 'NRS-484B-270-1', 'C111260', 'motor_vehicle_driver'):
        raise ValueError('exact bicycle package identity mismatch')
    selected = config.get('selected_case_id')
    if selected not in CASES or set(config.get('supported_case_ids', [])) != CASES:
        raise ValueError('exact bicycle case selection mismatch')
    if (config.get('rate_hz'), config.get('duration_s'),
            config.get('frame_count')) != (20, 45, 900):
        raise ValueError('exact bicycle capture timebase mismatch')
    cameras = config.get('cameras', [])
    if [(item.get('name'), item.get('width'), item.get('height'))
            for item in cameras] != [
            ('overview', 1920, 1080), ('approach', 1280, 720),
            ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]:
        raise ValueError('four original camera profile mismatch')
    scale = config.get('rider_throttle_scale', 1.0)
    if not isinstance(scale, (int, float)) or not 1.0 <= scale <= 1.25:
        raise ValueError('candidate rider throttle scale outside bounded engineering range')
    return selected


def encode_originals(attempt, capture, first_native_frame):
    codes = {}
    for view in VIEWS:
        image_pattern = capture / 'camera-originals' / view / '%08d.png'
        video = capture / (view + '.mkv')
        command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                   '-framerate', '20', '-start_number', str(first_native_frame),
                   '-i', str(image_pattern), '-frames:v', '900', '-an',
                   '-c:v', 'ffv1', '-pix_fmt', 'yuv444p', str(video)]
        result = subprocess.run(command, capture_output=True, timeout=3600)
        codes[view] = result.returncode
        if result.returncode != 0 or not video.is_file():
            raise ValueError('original camera encoding failed: ' + view +
                             result.stderr.decode('utf-8', 'replace')[-500:])
        shutil.copyfile(video, attempt / (view + '.mkv'))
    return codes


def run(output_dir, host, port, selected):
    import carla
    from worker_exchange.native_output import seal_capture

    attempt = Path(output_dir).resolve()
    site_root = os.environ.get('C111260_SITE_ROOT')
    if not site_root:
        raise ValueError('C111260_SITE_ROOT reviewed site directory required')
    site_root = Path(site_root).resolve()
    suffix = selected.removeprefix(ASSIGNMENT + '__')
    variant = CASE_VARIANTS[suffix]
    mode = variant['mode']
    site_path = site_root / (suffix + '.json')
    if not site_path.is_file() or site_path.is_symlink():
        raise ValueError('exact reviewed bicycle site packet missing')
    site = json.loads(site_path.read_text(encoding='utf-8'))
    if site.get('case_id') != selected:
        raise ValueError('reviewed bicycle site case mismatch')
    if site.get('rider_kind') != variant['rider_kind']:
        raise ValueError('reviewed rider modality differs from selected case')
    verify_site(site, site_root)
    client = carla.Client(host, port)
    client.set_timeout(30.0)
    world = client.get_world()
    map_ref = next(ref for ref in site['original_sources']
                   if ref['path'] == site['map_source_path'])
    map_packet = json.loads(read_source(map_ref, site_root).read_text(encoding='utf-8'))
    raw = map_packet.get('native_opendrive')
    if not raw:
        raise ValueError('reviewed original OpenDRIVE missing')
    read_source(raw, site_root)
    if hashlib.sha256(world.get_map().to_opendrive().encode('utf-8')).hexdigest() != raw['sha256']:
        raise ValueError('live Native OpenDRIVE differs from reviewed source')
    capture = attempt / 'capture'
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    receipt = capture_native(world, carla, site, site_root, capture,
                             mode, frames=900, case_id=selected,
                             rider_throttle_scale=config.get('rider_throttle_scale', 1.0))
    for name in ('trace.jsonl', 'video_frames.jsonl'):
        shutil.copyfile(capture / name, attempt / name)
    codes = encode_originals(attempt, capture, receipt['first_native_frame'])
    build_index(capture, selected)
    (attempt / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'source_index_sha256': sha(capture / 'source-index.json')}, indent=2) + '\n',
        encoding='utf-8')
    seal_capture(attempt, frames=900, restoration=receipt['restoration'],
                 errors=[], encoder_exit_codes=codes,
                 context={'case_id': selected,
                          'source_index_sha256': sha(capture / 'source-index.json')})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    selected = check()
    if args.check:
        return 0
    if args.output_dir is None:
        raise ValueError('Native attempt output directory required')
    try:
        run(args.output_dir, args.host, args.port, selected)
    except Exception as error:
        (args.output_dir / 'native-run-status.json').write_text(json.dumps({
            'errors': [str(error)], 'capture_complete': False,
            'selected_case_id': selected}, indent=2) + '\n', encoding='utf-8')
        raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
