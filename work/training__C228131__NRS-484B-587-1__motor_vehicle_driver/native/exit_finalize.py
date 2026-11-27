"""Unselected exit candidate: source-bound saved facts, without a legal verdict.

This is a portable candidate for an eligible exit-road assignment. It does not
change the frozen C228131 enter-road selection or certify original authority.
"""
import hashlib
import json
from pathlib import Path

from exit_candidate import CAMERAS, measure

AUTHORITY = ('access-authority.txt', 'device-authority.txt', 'device-content.txt',
             'device-erection.txt', 'exit-extent.txt')
SOURCES = ('road.xodr', 'access-review.json', 'device-review.json',
           'actor-poses.jsonl', 'video_frames.jsonl', *AUTHORITY)


def _required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing original exit source: ' + name)
    return path


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def observation(root):
    """Measure an exit only after separate access/device source hash joins."""
    root = Path(root)
    paths = {name: _required(root, name) for name in SOURCES}
    for name in CAMERAS:
        _required(root, name + '.mkv')
    raw = {name: path.read_bytes() for name, path in paths.items()}
    access = json.loads(raw['access-review.json'])
    device = json.loads(raw['device-review.json'])
    diagnostic = (root / 'fixture-provenance.json').is_file()
    required_status = 'synthetic_diagnostic' if diagnostic else 'independently_reviewed'
    if access.get('review_status') != required_status or device.get('review_status') != required_status:
        raise ValueError('Independent exit access/device reviews required')
    if not access.get('reviewer') or not device.get('reviewer') or access.get('source') == device.get('source'):
        raise ValueError('Distinct exit review sources required')
    road_sha = _sha(raw['road.xodr'])
    if access.get('road_sha256') != road_sha or device.get('road_sha256') != road_sha:
        raise ValueError('Exit road/review source differs')
    if access.get('pose_sha256') != _sha(raw['actor-poses.jsonl']):
        raise ValueError('Exit pose/access review source differs')
    if device.get('frame_map_sha256') != _sha(raw['video_frames.jsonl']):
        raise ValueError('Exit frame/device review source differs')
    for name in AUTHORITY:
        owner = access if name == 'access-authority.txt' else device
        if owner.get('source_sha256', {}).get(name) != _sha(raw[name]):
            raise ValueError('Exit authority source differs: ' + name)
    context = {
        'source_kind': 'synthetic_cpu' if diagnostic else 'original_native',
        'road_source_sha256': road_sha,
        'controlled_access_designation_sha256': _sha(raw['access-authority.txt']),
        'official_device_authority_sha256': _sha(raw['device-authority.txt']),
        'device_content_sha256': _sha(raw['device-content.txt']),
        'device_erection_sha256': _sha(raw['device-erection.txt']),
        'exit_extent_source_sha256': _sha(raw['exit-extent.txt']),
        'controlled_access_highway': access.get('controlled_access_highway'),
        'device_official': device.get('device_official'),
        'device_erected': device.get('device_erected'),
        'device_indicates_exit': device.get('device_indicates_exit'),
        'highway_edge_y_m': access.get('highway_edge_y_m'),
        'indicated_exit_x_interval_m': device.get('indicated_exit_x_interval_m'),
    }
    facts = measure(raw['actor-poses.jsonl'], raw['video_frames.jsonl'],
                    json.dumps(context, sort_keys=True).encode(), raw['road.xodr'])
    facts['source_sha256'] = {name: _sha(data) for name, data in raw.items()}
    facts['access_review_status'] = access['review_status']
    facts['device_review_status'] = device['review_status']
    facts['video_decode_verified'] = False
    facts['original_device_pixels_verified'] = False
    return facts
