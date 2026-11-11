"""Audit retained headlamp acquisition and full original-camera decodes."""

from hashlib import sha256
import json
from pathlib import Path

from headlamp_finalizer import analyze


SOURCES = ('video_frames.jsonl', 'trace.jsonl', 'following_footprints.jsonl',
           'headlamp_readbacks.jsonl', 'roadway_environment.jsonl',
           'lighting_context.json')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit_attempt(attempt, report, *, decoder=None):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    original = report['measurements']['headlamp_following_observation']
    if set(original['sources']) != set(SOURCES):
        raise ValueError('Analysis source inventory incomplete')
    for name in SOURCES:
        if not (root / name).is_file() or digest(root / name) != original['sources'][name]:
            raise ValueError('Stale or missing original source: ' + name)
    independent = analyze(root)
    if (independent['case_id'] != report['case_id'] or
            independent['measurements'] != report['measurements'] or
            independent['roadway_environment_observations'] != report['roadway_environment_observations']):
        raise ValueError('Saved analysis differs from recomputed originals')
    mapping = [json.loads(row) for row in (root / 'video_frames.jsonl').read_text().splitlines()]
    if decoder is None:
        from worker_exchange.media import audit as decoder
    cameras = {}
    for name in CAMERAS:
        path = root / (name + '.mkv')
        if not path.is_file():
            raise ValueError('Missing named original camera: ' + name)
        decoded = decoder(path, len(mapping), mapping_sha256=digest(root / 'video_frames.jsonl'))
        if decoded.get('frames') != len(mapping):
            raise ValueError('Incomplete source camera decode: ' + name)
        cameras[name] = {'source_sha256': digest(path), 'decode': decoded}
    return {'format': 'worker-headlamp-source-audit', 'case_id': report['case_id'],
            'original_source_hashes': original['sources'], 'frame_count': len(mapping),
            'camera_decodes': cameras, 'measurement_recomputed': True,
            'physical_visibility_claimed': False, 'legal_acceptance_claimed': False}
