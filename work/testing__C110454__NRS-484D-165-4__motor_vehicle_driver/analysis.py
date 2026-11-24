"""Source-bound saved measurements for the parked-headlamp cases.

Readback and pixel contrast are factual observations. Neither establishes a
statutory parking, lighted, depressed, or dimmed conclusion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lamp_probe import measure as measure_lamp_readback
from lamp_photometry import measure as measure_pixels, measure_video

ASSIGNMENT = 'testing__C110454__NRS-484D-165-4__motor_vehicle_driver'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def source(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def hashes(root: Path, names: tuple[str, ...]) -> dict[str, str]:
    return {name: hashlib.sha256(source(root, name).read_bytes()).hexdigest()
            for name in names}


def measure_parked_vehicle(site: dict, original: dict, pixels: dict | None) -> dict:
    return {'actor_id': original['actor_id'],
            'observed_frame_count': original['frame_count'],
            'parking_brake_and_footprint_sample_count': original['parked_sample_count'],
            'parking_geometry_source': site['parking_source_ref'],
            'intersection_geometry_source': site['intersection_source_ref'],
            'legal_parking_verdict': None}


def measure_lighted_headlamps(site: dict, original: dict, pixels: dict | None) -> dict:
    if pixels is None:
        raise ValueError('Missing required source: lamp-roi.json')
    return {'low_beam_readback_count': original['low_beam_readback_count'],
            'high_beam_readback_count': original['high_beam_readback_count'],
            'original_pixel_frame_count': pixels['frame_count'],
            'original_camera_view': pixels['camera_view'],
            'emitted_intensity_confirmed': False,
            'legal_lighted_verdict': None}


def measure_depressed_or_dimmed(site: dict, original: dict, pixels: dict | None) -> dict:
    if pixels is None:
        raise ValueError('Missing required source: lamp-roi.json')
    values = [row['lamp_minus_background_8bit'] for row in pixels['frames']]
    return {'mean_lamp_background_contrast_8bit': round(sum(values) / len(values), 4),
            'roi_sha256': pixels['roi_sha256'],
            'beam_aim_confirmed': False, 'calibrated_intensity_confirmed': False,
            'legal_dimming_verdict': None}


def build(attempt: str | Path) -> dict:
    root = Path(attempt).resolve(strict=True)
    config = json.loads(source(root, 'config.json').read_text(encoding='utf-8'))
    case_id = config['selected_case_id']
    mode = case_id.removeprefix(ASSIGNMENT + '__')
    if case_id != ASSIGNMENT + '__' + mode or mode not in ('unlit', 'low_beam', 'high_beam'):
        raise ValueError('exact parked-headlamp case differs')
    site = json.loads(source(root, 'site-packet.json').read_text(encoding='utf-8'))
    receipt = json.loads(source(root, 'native-source-receipt.json').read_text(encoding='utf-8'))
    if (site.get('case_id') != case_id or receipt.get('case_id') != case_id or
            receipt.get('requested_mode') != mode or
            receipt.get('site_source_sha256') != hashes(root, ('site-packet.json',))['site-packet.json'] or
            receipt.get('physical_acceptance_claimed') is not False):
        raise ValueError('original site/receipt provenance differs')
    actual = hashes(root, ('actor-state.jsonl', 'camera-frame-map.jsonl'))
    if receipt.get('source_hashes') != actual:
        raise ValueError('original actor/camera hashes differ')
    original = measure_lamp_readback(root, actual, mode=mode,
                                     low_beam_bit=receipt['light_masks']['low_beam'],
                                     high_beam_bit=receipt['light_masks']['high_beam'])
    if original['frame_count'] != receipt['frame_count']:
        raise ValueError('original frame count differs')
    media = receipt.get('original_camera_media')
    if not isinstance(media, dict) or set(media) != set(VIEWS):
        raise ValueError('four original camera sources required')
    for view in VIEWS:
        item = media[view]
        if item['source_frame_count'] != original['frame_count'] or hashes(root, (item['path'],))[item['path']] != item['sha256']:
            raise ValueError('original camera media differs: ' + view)
    pixel_data = None
    if mode != 'unlit':
        roi_path = source(root, 'lamp-roi.json')
        roi = json.loads(roi_path.read_text(encoding='utf-8'))
        view = roi['camera_view']
        camera_rows = [json.loads(line) for line in source(root, 'camera-frame-map.jsonl').read_text().splitlines()]
        pixel_method = measure_video if media[view]['path'].endswith('.mkv') else measure_pixels
        pixel_data = pixel_method(root, roi_path, hashes(root, ('lamp-roi.json',))['lamp-roi.json'],
                                  media[view], camera_rows,
                                  expected_frames=original['frame_count'],
                                  expected_dimensions=tuple(config['camera_dimensions'][view]))
    specs = [('parked_vehicle_observation', measure_parked_vehicle,
              ('site-packet.json', 'native-source-receipt.json', 'actor-state.jsonl',
               'camera-frame-map.jsonl'))]
    if mode != 'unlit':
        specs.extend([
            ('lighted_headlamp_observation', measure_lighted_headlamps,
             ('native-source-receipt.json', 'actor-state.jsonl', 'camera-frame-map.jsonl',
              'lamp-roi.json', media[pixel_data['camera_view']]['path'])),
            ('depression_or_dimming_observation', measure_depressed_or_dimmed,
             ('lamp-roi.json', media[pixel_data['camera_view']]['path'],
              'camera-frame-map.jsonl')),
        ])
    values = {name: {'value': method(site, original, pixel_data),
                     'method': method.__name__, 'sources': hashes(root, files)}
              for name, method, files in specs}
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'measurements': values, 'analysis_complete': True,
            'legal_verdict_claimed': False,
            'limitations': ['Original beam emission, aim and legal interpretation require independent review.']}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('analysis output already exists')
    report = build(args.attempt)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if (Path(args.attempt) / 'capture' / 'manifest.json').is_file():
        from native_publication import publish
        from worker_exchange.native_output import write_result
        write_result(args.attempt, publish(args.attempt, report))


if __name__ == '__main__':
    main()
