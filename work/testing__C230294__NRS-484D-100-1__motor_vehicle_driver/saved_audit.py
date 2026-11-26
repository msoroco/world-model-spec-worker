"""Independent saved-source audit for original lamp and device evidence."""

import hashlib
import json
from pathlib import Path

from lamp_direction import measure_original, require
from native_acquisition import CAMERAS
from source_packet import ASSIGNMENT, verify


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def audit_saved(attempt, case_name):
    """Reject missing or changed original sources before any acceptance claim."""
    attempt = Path(attempt).resolve()
    source = verify(attempt / 'lamp-context-packet.json', case_name)
    packet = source['packet']
    for field, checksum in source['source_sha256'].items():
        path = (attempt / packet['sources'][field]['path']).resolve()
        require(path.is_file() and digest(path) == checksum,
                'saved original context source missing or changed: ' + field)
    ticks_path = attempt / 'original-lamp-ticks.jsonl'
    require(ticks_path.is_file(), 'saved original lamp ticks missing')
    original_rows = rows(ticks_path)
    measured = measure_original(original_rows, packet['scene'], source['case'])
    manifest_path = attempt / 'camera-source-manifest.json'
    require(manifest_path.is_file(), 'saved camera source manifest missing')
    manifest = json.loads(manifest_path.read_text())
    require(manifest.get('case_id') == ASSIGNMENT + '__' + case_name and
            set(manifest.get('cameras', {})) == set(CAMERAS),
            'saved camera source identity missing')
    sensor_ids = set()
    for name in CAMERAS:
        entries = manifest['cameras'][name]
        require(isinstance(entries, list) and len(entries) == 900,
                'saved camera original frame count missing: ' + name)
        ids = {entry.get('sensor_id') for entry in entries}
        require(len(ids) == 1 and next(iter(ids)),
                'saved camera sensor identity changed: ' + name)
        sensor_ids.update(ids)
        for index, entry in enumerate(entries):
            path = (attempt / entry.get('path', '')).resolve()
            require(path.is_relative_to(attempt) and path.is_file() and
                    entry.get('original_frame') == original_rows[index]['original_frame'] and
                    entry.get('sha256') == digest(path),
                    'saved original camera source missing or changed: ' + name)
    require(len(sensor_ids) == 4, 'four distinct original camera sensors missing')
    release_path = attempt / 'native-owner-release.json'
    require(release_path.is_file(), 'Native owner release missing')
    release = json.loads(release_path.read_text())
    require(release.get('case_id') == manifest['case_id'] and
            release.get('world_restored') is True and
            release.get('last_original_frame') == original_rows[-1]['original_frame'] and
            release.get('owned_actor_ids') and
            len(set(release['owned_actor_ids'])) == len(release['owned_actor_ids']),
            'Native release or restoration evidence missing')
    report_path = attempt / 'lamp-measurement.json'
    require(report_path.is_file(), 'saved original lamp measurement missing')
    report = json.loads(report_path.read_text())
    require(report.get('case_id') == measured['case_id'] and
            report.get('lamp_on_frame_counts') == measured['lamp_on_frame_counts'] and
            report.get('source_packet_sha256') == source['packet_sha256'],
            'saved lamp measurement differs from original evidence')
    return {'case_id': manifest['case_id'], 'frame_count': 900,
            'camera_count': 4, 'source_packet_sha256': source['packet_sha256'],
            'legal_judgment': None, 'physical_acceptance_claimed': False}
