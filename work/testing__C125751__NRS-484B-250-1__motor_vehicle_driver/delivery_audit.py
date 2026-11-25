"""Independent local delivery gate for original C125751 signal crossings.

CPU fixtures may exercise rejection paths. Only original reviewed Native bytes,
full media decode, human pixel review and Core time joins can pass production.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from case_protocol import ASSIGNMENT, SUFFIXES
from saved_signal_audit import audit as audit_history
from signal_crossing import validate_source_packet
from source_bindings import validate_review_refs


CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')
REQUIRED = ('construction.json', 'config.json', 'runner.py',
            'acquisition-provenance.json', 'source-packet.json',
            'review.json', 'map.xodr', 'signal-packet.json',
            'signal-history.json', 'trace.jsonl', 'video_frames.jsonl', *CAMERAS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def verify_sources(case_id, attempt):
    attempt = Path(attempt).resolve()
    if case_id not in {ASSIGNMENT + '__' + suffix for suffix in SUFFIXES}:
        raise ValueError('unknown exact case')
    seal = read(attempt / 'capture-seal.json')
    if (seal.get('provenance_kind') != 'native' or seal.get('diagnostic_fixture') is not False or
            seal.get('events') != ['capture_finished', 'encoders_closed', 'restoration_verified'] or
            seal.get('restoration', {}).get('restored') is not True):
        raise ValueError('original Native lifecycle unverified')
    sealed = seal.get('sources', {})
    for name in REQUIRED:
        path = attempt / name
        if not path.is_file() or sealed.get(name) != sha(path):
            raise ValueError('sealed Native source missing or changed: ' + name)
    acquisition = read(attempt / 'acquisition.json')
    provenance = read(attempt / 'acquisition-provenance.json')
    if (provenance.get('provenance_kind') != 'native' or
            provenance.get('diagnostic_fixture') is not False or
            provenance.get('review_sha256') != sealed['review.json']):
        raise ValueError('original acquisition provenance unverified')
    for name in REQUIRED:
        if name in ('construction.json', 'config.json', 'runner.py'):
            continue
        entry = acquisition.get(name, {})
        if entry.get('kind') != 'original_native' or entry.get('sha256') != sealed[name]:
            raise ValueError('original acquisition binding differs: ' + name)
    config = read(attempt / 'config.json')
    construction = read(attempt / 'construction.json')
    if config.get('selected_case_id') != case_id or construction.get('case_id') != case_id:
        raise ValueError('sealed construction/config selected another exact case')
    source_packet = read(attempt / 'source-packet.json')
    validate_source_packet(source_packet, (attempt / 'map.xodr').read_bytes(),
                           (attempt / 'review.json').read_bytes())
    for ref in validate_review_refs((attempt / 'review.json').read_bytes(), attempt):
        if sealed.get(ref['path']) != sha(attempt / ref['path']):
            raise ValueError('reviewed original source not sealed: ' + ref['path'])
    signal_packet = read(attempt / 'signal-packet.json')
    if (signal_packet.get('map_sha256') != source_packet['map_sha256'] or
            signal_packet.get('review_sha256') != source_packet['review_sha256'] or
            signal_packet.get('crossing_id') != source_packet['crossing_id'] or
            signal_packet.get('expected_frames') != config.get('duration_frames')):
        raise ValueError('original signal history source/capture contract differs')
    observed = audit_history(signal_packet, (attempt / 'signal-history.json').read_bytes(),
                             case_id, sha(attempt / 'review.json'))
    mapping = [json.loads(s) for s in (attempt / 'video_frames.jsonl').read_text().splitlines() if s]
    trace = [json.loads(s) for s in (attempt / 'trace.jsonl').read_text().splitlines() if s]
    frames = read(attempt / 'signal-history.json')['frames']
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(frames):
        raise ValueError('original Native participant/frame counts differ')
    for i, (mapped, row, signal) in enumerate(zip(mapping, trace, frames)):
        if (mapped.get('video_frame') != i or mapped.get('carla_frame') != row.get('frame') or
                abs(mapped.get('time_s', -1) - row.get('time_s', -2)) > 1e-6 or
                abs(signal['time_s'] - row['time_s']) > 1e-6):
            raise ValueError('original Native participant/frame time join differs')
    return {'seal_sha256': sha(attempt / 'capture-seal.json'),
            'result_sha256': sha(attempt / 'result.json'),
            'observed': observed, 'frames': mapping,
            'source_hashes': {name: sealed[name] for name in REQUIRED}}


def verify_physical(case_id, attempt, source, result):
    if (result.get('case_id') != case_id or
            result.get('provenance_kind') != 'native' or
            result.get('diagnostic_fixture') is not False or
            result.get('setup_confirmed') is not True or
            result.get('maneuver_completed') is not True):
        raise ValueError('physical completion unverified')
    checks = result.get('physical_checks', {})
    if any(checks.get(name, {}).get('status') != 'met' for name in
           ('setup', 'target', 'maneuver', 'attempt')):
        raise ValueError('physical completion check did not pass')
    for check in checks.values():
        hashes = check.get('sources', {})
        if not hashes or any(source['source_hashes'].get(name) != digest or
                             sha(Path(attempt) / name) != digest
                             for name, digest in hashes.items()):
            raise ValueError('physical completion source binding differs')


def verify_media(attempt, source, decode, media_auditor):
    attempt = Path(attempt)
    video = attempt / 'raw.mkv'
    mapping = attempt / 'video_frames.jsonl'
    if (not video.is_file() or decode.get('format') != 'source-decode' or
            decode.get('passed') is not True or
            decode.get('video_sha256') != sha(video) or
            decode.get('mapping_sha256') != sha(mapping) or
            decode.get('frames') != len(source['frames']) or
            decode.get('checks', {}).get('frame_count') != 'all-decoded-frames' or
            decode.get('auditor_sha256') != sha(media_auditor)):
        raise ValueError('full original video decode unverified')


def verify_pixels(case_id, attempt, source, pixels):
    attempt = Path(attempt)
    video = attempt / 'raw.mkv'
    mapping = attempt / 'video_frames.jsonl'
    trace = attempt / 'traffic_spec' / 'trace.json'
    if (pixels.get('format') != 'worker-original-pixel-review' or
            pixels.get('case_id') != case_id or
            pixels.get('diagnostic_fixture') is not False or
            not pixels.get('reviewer') or
            pixels.get('video_sha256') != sha(video) or
            pixels.get('frame_map_sha256') != sha(mapping) or
            pixels.get('core_trace_sha256') != sha(trace)):
        raise ValueError('actual original pixel review missing or stale')
    for key in ('ego', 'other', 'crossing', 'signal'):
        item = pixels.get('observations', {}).get(key, {})
        frame = item.get('frame')
        if (item.get('visible') is not True or type(frame) is not int or
                not 0 <= frame < len(source['frames']) or
                item.get('view') not in ('overview', 'approach',
                                        'reference_corner', 'driver_reference') or
                not item.get('description')):
            raise ValueError('actual pixels unverified: ' + key)


def verify_core(attempt, source):
    core = read(Path(attempt) / 'traffic_spec' / 'trace.json')
    scenes = core.get('scenes')
    if not isinstance(scenes, list) or len(scenes) != len(source['frames']):
        raise ValueError('Core trace and original frame count differ')
    for scene, frame in zip(scenes, source['frames']):
        if scene.get('t') != round(frame['time_s'] * 1000):
            raise ValueError('Core trace and original frame time join differs')


def audit_delivery(case_id, attempt, physical_receipt, pixel_review,
                   decode_receipt, media_auditor, job_id, attempt_number,
                   recording_id):
    attempt = Path(attempt).resolve()
    if Path(physical_receipt).resolve() != (attempt / 'result.json').resolve():
        raise ValueError('physical receipt must be the saved result')
    source = verify_sources(case_id, attempt)
    physical = read(physical_receipt)
    verify_physical(case_id, attempt, source, physical)
    decode = read(decode_receipt)
    verify_media(attempt, source, decode, media_auditor)
    verify_core(attempt, source)
    pixels = read(pixel_review)
    verify_pixels(case_id, attempt, source, pixels)
    auditor = Path(__file__).resolve()
    return {'format': 'worker-delivery-audit', 'passed': True,
            'case_id': case_id, 'job_id': job_id, 'attempt': attempt_number,
            'recording_id': recording_id, 'checks': {name: True for name in CHECKS},
            'frames': len(source['frames']), 'video': 'raw.mkv',
            'video_sha256': sha(attempt / 'raw.mkv'),
            'trace': 'traffic_spec/trace.json',
            'trace_sha256': sha(attempt / 'traffic_spec' / 'trace.json'),
            'frame_map_sha256': sha(attempt / 'video_frames.jsonl'),
            'source_result_sha256': source['result_sha256'],
            'capture_seal_sha256': source['seal_sha256'],
            'auditor_path': str(auditor), 'auditor_sha256': sha(auditor),
            'source_decode_receipt_path': str(Path(decode_receipt).resolve()),
            'source_decode_receipt_sha256': sha(decode_receipt),
            'source_decode_auditor_sha256': sha(media_auditor),
            'pixel_review_sha256': sha(pixel_review)}


def main():
    parser = argparse.ArgumentParser()
    for name in ('case-id', 'job-id', 'recording-id'):
        parser.add_argument('--' + name, required=True)
    for name in ('attempt', 'physical-receipt', 'pixel-review', 'decode-receipt',
                 'media-auditor', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--attempt-number', type=int, required=True)
    args = parser.parse_args()
    result = audit_delivery(args.case_id, args.attempt, args.physical_receipt,
                            args.pixel_review, args.decode_receipt,
                            args.media_auditor, args.job_id,
                            args.attempt_number, args.recording_id)
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
