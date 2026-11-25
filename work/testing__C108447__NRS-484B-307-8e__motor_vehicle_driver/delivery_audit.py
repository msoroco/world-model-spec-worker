"""Independent saved original-source, pixel and route-completion audit.

This command reads a sealed Native attempt after owner release. It never drives
CARLA or decides the legal question. Synthetic fixtures can test it, but cannot
establish that a parcel authority or recording is original.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from physical_completion import evaluate
from saved_delivery import CAMERAS, PROFILE, audit as audit_sources
from saved_delivery import source_file


def audit(attempt: Path, bundle: dict, *, expected_frames: int = 900) -> dict:
    source = audit_sources(attempt, bundle, expected_frames=expected_frames)
    map_path = source_file(attempt, bundle['map'], 'map')
    trace_path = source_file(attempt, bundle['trace'], 'trace')
    completion = evaluate(json.loads(map_path.read_text()), json.loads(trace_path.read_text()), bundle['case_id'])
    if completion['status'] != 'met':
        raise ValueError('Original physical route completion required: ' + completion['status'])
    return {'format': 'property-original-delivery-audit-v1',
            'case_id': bundle['case_id'], 'frame_count': source['frame_count'],
            'original_source_audit': source, 'physical_completion': completion,
            'map_sha256': hashlib.sha256(map_path.read_bytes()).hexdigest(),
            'trace_sha256': hashlib.sha256(trace_path.read_bytes()).hexdigest(),
            'physical_acceptance_claimed': False, 'legal_judgment': None}


def audit_production(canonical: Path, attempt: Path, bundle_path: Path,
                     pixel_review: Path, *, expected_frames: int = 900) -> dict:
    """Bind original pixels, encoded videos and a separate visual review."""
    canonical = canonical.resolve()
    attempt = attempt.resolve()
    if attempt != canonical / 'original-attempt':
        raise ValueError('canonical original attempt path required')
    if bundle_path.resolve() != attempt / 'delivery-bundle.json':
        raise ValueError('sealed original delivery bundle path required')
    if not canonical.is_dir() or bundle_path.is_symlink() or pixel_review.is_symlink():
        raise ValueError('regular canonical capture and review files required')
    bundle = json.loads(bundle_path.read_text())
    original = audit(attempt, bundle, expected_frames=expected_frames)
    seal_path = canonical / 'capture-seal.json'
    if not seal_path.is_file() or seal_path.is_symlink():
        raise ValueError('canonical Native capture seal required')
    seal = json.loads(seal_path.read_text())
    if (seal.get('format') != 'worker-sealed-capture' or
            seal.get('provenance_kind') != 'native' or
            seal.get('diagnostic_fixture') is not False or
            seal.get('frames') != expected_frames or
            seal.get('restoration', {}).get('owner_release_readback', {}).get('readback_passed') is not True):
        raise ValueError('released original Native capture seal required')
    sources = seal.get('sources', {})
    if sources.get('original-attempt/delivery-bundle.json') != _sha(bundle_path):
        raise ValueError('original bundle differs from canonical capture seal')
    mapping = canonical / 'video_frames.jsonl'
    if not mapping.is_file() or mapping.is_symlink() or sources.get('video_frames.jsonl') != _sha(mapping):
        raise ValueError('canonical video frame map seal required')
    rows = [json.loads(line) for line in mapping.read_text().splitlines()]
    original_rows = [json.loads(line) for line in (attempt / 'frame-map.jsonl').read_text().splitlines()]
    if len(rows) != expected_frames or any(
            row.get('video_frame') != index or
            row.get('native_frame') != source.get('frame') or
            row.get('carla_frame') != source.get('frame') or
            abs(row.get('time_s', -1) - source.get('time_s', -2)) > 0.002
            for index, (row, source) in enumerate(zip(rows, original_rows))):
        raise ValueError('canonical video frames differ from original pixels')
    video_hashes = {}
    for camera in CAMERAS:
        video = canonical / (camera + '.mkv')
        if not video.is_file() or video.is_symlink():
            raise ValueError('canonical encoded video missing: ' + camera)
        video_hashes[camera] = _sha(video)
        if sources.get(video.name) != video_hashes[camera]:
            raise ValueError('canonical encoded video seal differs: ' + camera)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                                '-select_streams', 'v:0', '-show_entries',
                                'stream=nb_read_frames,width,height',
                                '-of', 'json', str(video)], capture_output=True, text=True)
        if probe.returncode != 0:
            raise ValueError('canonical video probe failed: ' + camera)
        streams = json.loads(probe.stdout).get('streams', [])
        if len(streams) != 1 or int(streams[0].get('nb_read_frames', -1)) != expected_frames:
            raise ValueError('canonical video frame count differs: ' + camera)
        if expected_frames == 900 and (streams[0].get('width'), streams[0].get('height')) != PROFILE[camera]:
            raise ValueError('canonical video profile differs: ' + camera)
        decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video),
                                  '-map', '0:v:0', '-f', 'null', '-'],
                                 capture_output=True)
        if decoded.returncode != 0:
            raise ValueError('canonical video full decode failed: ' + camera)
    if not pixel_review.is_file():
        raise ValueError('separate original pixel review receipt required')
    review = json.loads(pixel_review.read_text())
    if (review.get('format') != 'original-pixel-review-v1' or
            review.get('decision') != 'reviewed' or
            review.get('case_id') != bundle['case_id'] or
            review.get('frame_count') != expected_frames or
            review.get('bundle_sha256') != _sha(bundle_path) or
            review.get('capture_seal_sha256') != _sha(seal_path) or
            review.get('video_sha256') != video_hashes or
            not review.get('reviewer') or not review.get('source_record_id') or
            not review.get('reviewed_at') or
            set(review.get('reviewed_views', {})) != set(CAMERAS) or
            any(not view.get('visible_subjects') or not view.get('frame_range') or
                not view.get('reviewer_note')
                for view in review['reviewed_views'].values())):
        raise ValueError('separate reviewed original pixels and video hashes required')
    return {**original, 'canonical_video_sha256': video_hashes,
            'original_pixel_review_sha256': _sha(pixel_review),
            'canonical_full_video_decode': True,
            'physical_acceptance_claimed': False}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-frames', type=int, default=900)
    parser.add_argument('--canonical-root', type=Path, required=True)
    parser.add_argument('--pixel-review', type=Path, required=True)
    args = parser.parse_args()
    bundle = json.loads(args.bundle.read_text())
    if bundle.get('case_id') != args.case:
        raise ValueError('Exact original audit case differs')
    result = audit_production(args.canonical_root, args.attempt, args.bundle,
                              args.pixel_review, expected_frames=args.expected_frames)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': args.case, 'source_and_pixels': 'passed',
                      'route_completion': result['physical_completion']['status'],
                      'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
