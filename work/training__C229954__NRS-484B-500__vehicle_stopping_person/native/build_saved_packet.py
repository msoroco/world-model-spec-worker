"""Join immutable saved Native sources into the designated-place meter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from designated_stop import measure


def _required(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return path


def _read(path):
    path = _required(path)
    if path.suffix == '.jsonl':
        return [json.loads(line) for line in path.read_text().splitlines() if line]
    return json.loads(path.read_text())


def _ref(path):
    path = _required(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def packet_from_attempt(attempt):
    attempt = Path(attempt)
    review = _read(attempt / 'source-review.json')
    if review.get('source_kind') != 'original_official_device_review' or \
            not {'device', 'designation', 'map', 'route'} <= set(review.get('sources', {})):
        raise ValueError('Original official device source inventory missing')
    for name in ('device', 'designation', 'map', 'route'):
        expected = review['sources'][name]
        source = _required(attempt / ('source-' + name + '.json'))
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected.get('sha256'):
            raise ValueError('Changed original review source: ' + name)
    device = _read(attempt / 'source-device.json')
    designation = _read(attempt / 'source-designation.json')
    map_record = _read(attempt / 'source-map.json')
    activity = _read(attempt / 'person-activity.json')
    directions = _read(attempt / 'traffic-direction.json')
    rows = _read(attempt / 'native-stop-trace.jsonl')
    mapping = _read(attempt / 'video_frames.jsonl')
    if device.get('device_id') != designation.get('device_id'):
        raise ValueError('Original device and designation differ')
    packet_device = dict(device)
    packet_device['designated_polygon_map_m'] = designation.get('designated_polygon_map_m')
    packet_device['hazard_context_status'] = 'physical_facts_retained_legal_unresolved'
    packet = {'format': 'worker-designated-stop-native-packet',
              'device': packet_device, 'person_activity': activity,
              'traffic_direction': directions, 'rows': rows,
              'sources': {name: _ref(attempt / path) for name, path in {
                  'device': 'source-device.json',
                  'designation': 'source-designation.json',
                  'map': 'source-map.json',
                  'person_activity': 'person-activity.json',
                  'traffic_direction': 'traffic-direction.json',
                  'native_trace': 'native-stop-trace.jsonl',
                  'video_frame_map': 'video_frames.jsonl',
              }.items()}}
    return packet


def build(attempt):
    outcome = measure(packet_from_attempt(attempt))
    outcome['source_review_sha256'] = _ref(attempt / 'source-review.json')['sha256']
    return outcome
