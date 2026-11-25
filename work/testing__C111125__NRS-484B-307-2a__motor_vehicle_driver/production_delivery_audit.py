"""Fail-closed production audit of sealed Native sources and independent review."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from delivery_audit import VIEWS, PRODUCTION_PROFILE, audit_saved_delivery
from native_scene import source


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sealed_sources(attempt, packet):
    seal_path = attempt / 'capture-seal.json'
    seal = read(seal_path)
    require(seal.get('format') == 'worker-sealed-capture' and
            seal.get('provenance_kind') == 'native' and
            seal.get('diagnostic_fixture') is False and seal.get('frames') == 900,
            'original Native capture seal missing or diagnostic')
    require(seal.get('restoration', {}).get('restored') is True and
            seal.get('events') == ['capture_finished', 'encoders_closed', 'restoration_verified'] and
            seal.get('encoder_exit_codes') == {v: 0 for v in VIEWS},
            'capture lifecycle, restoration or encoder closure unverified')
    sources = seal.get('sources')
    require(isinstance(sources, dict) and sources, 'capture source inventory missing')
    canonical = json.dumps(sources, sort_keys=True, separators=(',', ':'),
                           ensure_ascii=False).encode()
    require(hashlib.sha256(canonical).hexdigest() == seal.get('source_digest'),
            'capture source digest differs')
    mandatory = {'original-green-packet.json', 'original-events.json',
                 'original-frame-map.json', 'site.json', 'trace.jsonl',
                 'video_frames.jsonl', 'acquisition.json',
                 'media-capture-receipt.json', 'source-frame-samples.json'}
    mandatory.update(v + '.mkv' for v in VIEWS)
    require(mandatory <= set(sources), 'sealed original source missing')
    for name, expected in sources.items():
        path = source({'path': name, 'sha256': expected}, attempt)
        require(path.is_file(), 'sealed source is not a file')
    revision = seal.get('native_revision', {})
    require(revision.get('runner_sha256') == sources.get('runner.py') and
            revision.get('construction_sha256') == sources.get('construction.json'),
            'Native construction revision differs')
    acquisition = read(attempt / 'acquisition.json')
    for name in ('original-green-packet.json', 'site.json',
                 'original-events.json', 'video_frames.jsonl'):
        require(acquisition.get(name) == {'kind': 'original_native',
                                          'sha256': sources[name]},
                'original Native acquisition binding differs: ' + name)
    media = read(attempt / 'media-capture-receipt.json')
    require(media.get('case_id') == packet['case_id'] and
            media.get('event_ref') == packet['event_ref'] and
            media.get('frame_map_ref') == packet['frame_map_ref'] and
            media.get('camera_media_refs') == packet['camera_media_refs'] and
            media.get('camera_capture_complete') is True and
            media.get('software_audit_passed') is True,
            'original media capture receipt differs')
    return seal, sha(seal_path)


def sampled_pixel_joins(attempt, packet):
    manifest_path = attempt / 'source-frame-samples.json'
    manifest = read(manifest_path)
    require(manifest.get('case_id') == packet['case_id'] and
            set(manifest.get('samples', {})) == set(VIEWS),
            'original PNG sample inventory differs')
    joined = {}
    for view in VIEWS:
        refs = manifest['samples'][view]
        require(set(refs) == {'0', '450', '899'},
                'original first, middle and last PNG samples required')
        joined[view] = {}
        width, height = PRODUCTION_PROFILE[view]
        video = source(packet['camera_media_refs'][view], attempt)
        for key, ref in refs.items():
            original = source(ref, attempt)
            with Image.open(original) as image:
                require(image.size == (width, height),
                        'original PNG sample dimensions differ')
                png_rgb = image.convert('RGB').tobytes()
            index = int(key)
            decoded = subprocess.run(
                ['ffmpeg', '-v', 'error', '-xerror', '-i', str(video),
                 '-vf', f'select=eq(n\\,{index})', '-vsync', '0',
                 '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                capture_output=True, check=True)
            require(len(decoded.stdout) == width * height * 3 and
                    decoded.stdout == png_rgb,
                    'original PNG-to-video pixel join differs: ' + view + '/' + key)
            joined[view][key] = hashlib.sha256(png_rgb).hexdigest()
    return sha(manifest_path), joined


def independent_review(attempt, case, seal_hash, result_hash, sample_hash,
                       joined, packet):
    path = attempt / 'independent-source-review.json'
    review = read(path)
    require(review.get('case_id') == case and review.get('reviewer_id') and
            review.get('reviewer_role') == 'independent_source_reviewer' and
            review.get('method') == 'manual_original_frame_and_event_review',
            'independent original-source review absent')
    expected = {'capture_seal_sha256': seal_hash,
                'saved_result_sha256': result_hash,
                'source_frame_samples_sha256': sample_hash,
                'original_events_sha256': packet['event_ref']['sha256'],
                'original_frame_map_sha256': packet['frame_map_ref']['sha256'],
                'camera_media_sha256': {v: packet['camera_media_refs'][v]['sha256']
                                        for v in VIEWS}}
    require(review.get('source_bindings') == expected,
            'independent review source binding stale')
    require(review.get('sample_rgb_sha256') == joined,
            'independent review did not inspect joined original pixels')
    observations = review.get('observations', {})
    frame_rows = read(source(packet['frame_map_ref'], attempt))
    original_frames = {row['frame'] for row in frame_rows}
    for name in ('official_circular_green_visible', 'other_user_context_reviewed',
                 'ego_yield_reviewed', 'physical_completion_reviewed',
                 'all_four_views_reviewed'):
        item = observations.get(name)
        require(isinstance(item, dict) and item.get('status') == 'met' and
                isinstance(item.get('explanation'), str) and
                len(item['explanation'].strip()) >= 20 and
                isinstance(item.get('original_frame_ids'), list) and
                item['original_frame_ids'] and
                all(type(frame) is int and frame in original_frames
                    for frame in item['original_frame_ids']),
                'independent original-source observation absent: ' + name)
    require(review.get('legal_verdict_claimed') is False,
            'independent review must not invent legal verdict')
    return {'path': path.name, 'sha256': sha(path)}


def run(case, attempt, processed):
    attempt = attempt.resolve()
    packet = read(attempt / 'original-green-packet.json')
    require(packet['case_id'] == case, 'wrong exact case')
    seal, seal_hash = sealed_sources(attempt, packet)
    receipt = audit_saved_delivery(packet, attempt)
    versions = sorted(processed.resolve().glob('v[0-9][0-9][0-9][0-9]'))
    require(len(versions) == 1, 'one reviewed saved processing revision required')
    result_path = versions[0] / 'analysis/result.json'
    result = read(result_path)
    require(result.get('case_id') == case and
            result.get('provenance_kind') == 'native',
            'saved result differs from original Native case')
    maneuver = result.get('physical_checks', {}).get('maneuver', {})
    require(maneuver.get('status') == 'met' and
            result.get('maneuver_completed') is True,
            'saved physical completion not demonstrated')
    require(all(maneuver.get('sources', {}).get(name) == seal['sources'][name]
                for name in ('config.json', 'trace.jsonl', 'video_frames.jsonl')),
            'saved physical completion source binding differs')
    sample_hash, joined = sampled_pixel_joins(attempt, packet)
    review_ref = independent_review(attempt, case, seal_hash,
        sha(result_path), sample_hash, joined, packet)
    value = {'case_id': case, 'source_audit': receipt,
             'capture_seal_sha256': seal_hash,
             'source_digest': seal['source_digest'],
             'saved_result_sha256': sha(result_path),
             'physical_check': maneuver,
             'sample_rgb_sha256': joined,
             'independent_review_ref': review_ref,
             'checks': ['native_source', 'all_participants', 'time_join',
                        'full_video_decode', 'actual_pixels', 'physical_completion'],
             'legal_verdict_claimed': False}
    print(json.dumps(value, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processed', type=Path, required=True)
    args = parser.parse_args()
    run(args.case, args.attempt, args.processed)
