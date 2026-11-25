"""Independent source and pixel audit of one sealed fire-lane original attempt.

This auditor is read-only. It reports evidence integrity and physical observations;
it never decides whether a statutory designation or exception legally applies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from saved_audit import audit_planned_case
from source_packet import validate_packet

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_capture(attempt: Path, case_id: str, *, allow_diagnostic: bool = False) -> dict:
    attempt = Path(attempt)
    inventory = json.loads((attempt / 'inventory.json').read_text())
    if inventory.get('case_id') != case_id:
        raise ValueError('original inventory case changed')
    diagnostic = inventory.get('diagnostic_fixture') is True
    if diagnostic and not allow_diagnostic:
        raise ValueError('synthetic capture cannot satisfy original delivery')
    if sha(attempt / 'history.jsonl') != inventory.get('history_sha256'):
        raise ValueError('original history changed')
    if sha(attempt / 'frame_map.json') != inventory.get('frame_map_sha256'):
        raise ValueError('original frame map changed')
    packet = attempt / 'reviewed-packet.json'
    if sha(packet) != inventory.get('site_sha256'):
        raise ValueError('reviewed packet changed')
    site = validate_packet(packet, case_id)
    if site != json.loads((attempt / 'site.json').read_text()):
        raise ValueError('reviewed site changed')
    report = audit_planned_case(attempt / 'history.jsonl', inventory['history_sha256'],
                                case_id, inventory['site_sha256'])
    rows = [json.loads(line) for line in (attempt / 'history.jsonl').read_text().splitlines()]
    mapping = json.loads((attempt / 'frame_map.json').read_text())['frames']
    if len(mapping) != len(rows):
        raise ValueError('original frame map length changed')
    for index, (row, frame) in enumerate(zip(rows, mapping)):
        if (row['original_frame'] != frame['frame'] or row['time_s'] != frame['time_s'] or
                frame['video_frame'] != index or
                row['frame_map_sha256'] != inventory['frame_map_sha256']):
            raise ValueError('original frame map/history identity changed')
    media = {}
    for name in CAMERAS:
        path = attempt / (name + '.zip')
        if sha(path) != inventory.get('camera_media', {}).get(name):
            raise ValueError('original camera archive changed: ' + name)
        with zipfile.ZipFile(path) as archive:
            entries = archive.namelist()
            if len(entries) != len(rows):
                raise ValueError('original camera archive frame count changed: ' + name)
            for index, row in enumerate(rows):
                expected = f'{index:04d}-{row["original_frame"]}.png'
                if entries[index] != expected:
                    raise ValueError('original camera archive order changed: ' + name)
                raw = archive.read(expected)
                if (not raw.startswith(b'\x89PNG\r\n\x1a\n') or
                        hashlib.sha256(raw).hexdigest() !=
                        row['camera_frames'][name]['source_sha256']):
                    raise ValueError('original camera pixel hash changed: ' + name)
        media[name] = inventory['camera_media'][name]
    return {'format': 'worker-original-fire-lane-capture-audit', 'case_id': case_id,
            'diagnostic_fixture': diagnostic, 'physical_acceptance_claimed': False,
            'legal_judgment': None, 'history_sha256': inventory['history_sha256'],
            'reviewed_packet_sha256': inventory['site_sha256'],
            'frame_map_sha256': inventory['frame_map_sha256'],
            'camera_archive_sha256': media, 'original_frames': len(rows),
            'observed': report['observed']}


def audit_saved_channels(attempt: Path, case_id: str, *, allow_diagnostic: bool = False) -> dict:
    """Independently join every saved channel row to its original Native frame.

    This checks source continuity, not sign legibility or legal classification.
    Synthetic process-saved fixtures require an explicit diagnostic opt-in.
    """
    attempt = Path(attempt)
    original = attempt / 'original-attempt'
    inventory = json.loads((original / 'inventory.json').read_text())
    if inventory.get('case_id') != case_id:
        raise ValueError('saved original case changed')
    diagnostic = inventory.get('diagnostic_fixture') is True
    if diagnostic and not allow_diagnostic:
        raise ValueError('synthetic saved source cannot satisfy original delivery')
    history = original / 'history.jsonl'
    if sha(history) != inventory.get('history_sha256'):
        raise ValueError('saved original history changed')
    rows = [json.loads(line) for line in history.read_text().splitlines()]
    if not rows or (not diagnostic and len(rows) != 900):
        raise ValueError('saved original frame count changed')
    frame_map = original / 'frame_map.json'
    if sha(frame_map) != inventory.get('frame_map_sha256'):
        raise ValueError('saved original frame map changed')
    mapping = json.loads(frame_map.read_text())['frames']
    if len(mapping) != len(rows):
        raise ValueError('saved original frame map count changed')
    trace = [json.loads(line) for line in (attempt / 'trace.jsonl').read_text().splitlines()]
    video = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    if len(trace) != len(rows) or len(video) != len(rows):
        raise ValueError('saved trace/video frame count changed')
    expected = {
        'designation_and_posting': lambda row: {
            'designation_sha256': row['fire_code_designation_sha256'],
            'posting_sha256': row['posting_authority_sha256'],
            'sign_present': row['sign_physically_present']},
        'curb_adjacency': lambda row: max(0, min(row['body_east_x_m'], row['posted_interval_m'][1]) -
                                            max(row['body_west_x_m'], row['posted_interval_m'][0])),
        'activity': lambda row: row['activity_observation'],
        'attendance': lambda row: row['attended_observation'],
        'property_status': lambda row: row['property_kind'],
        'necessity_exceptions': lambda row: row['exception_kind'],
    }
    channels = {name: [json.loads(line) for line in
                       (attempt / 'channels' / (name + '.jsonl')).read_text().splitlines()]
                for name in expected}
    if any(len(values) != len(rows) for values in channels.values()):
        raise ValueError('saved channel count changed')
    for index, row in enumerate(rows):
        frame = mapping[index]
        motion = trace[index]
        image = video[index]
        if (row['original_frame'] != frame['frame'] or row['time_s'] != frame['time_s'] or
                motion.get('frame') != frame['frame'] or motion.get('time_s') != frame['time_s'] or
                image.get('video_frame') != index or image.get('carla_frame') != frame['frame'] or
                image.get('time_s') != frame['time_s']):
            raise ValueError('saved original/trace/video identity changed')
        for name, measure in expected.items():
            value = channels[name][index]
            if value.get('time_s') != row['time_s'] or value.get('value') != measure(row):
                raise ValueError('saved channel differs from original: ' + name)
    return {'format': 'worker-fire-lane-saved-channel-audit', 'case_id': case_id,
            'diagnostic_fixture': diagnostic, 'physical_acceptance_claimed': False,
            'legal_judgment': None, 'original_frames': len(rows),
            'history_sha256': sha(history), 'frame_map_sha256': sha(frame_map),
            'channels_sha256': {name: sha(attempt / 'channels' / (name + '.jsonl'))
                                for name in expected}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit_capture(args.attempt, args.case,
                                   allow_diagnostic=args.allow_diagnostic),
                     indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
