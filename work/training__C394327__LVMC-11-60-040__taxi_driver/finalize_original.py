"""Join sealed original taxi sources; never infer passenger loading from requests."""
import hashlib
import json
from pathlib import Path

from taxi_loading import FRAMES, VIEWS, measure

REVIEW_FILES = ('taxi-license-review.json', 'stand-designation-review.json',
                'participant-activity-review.json', 'other-regulations-review.json')
SOURCE_FILES = ('native-rows.jsonl', 'video_frames.jsonl',
                'observed-activity.jsonl') + tuple(view + '.mkv' for view in VIEWS)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def _source(attempt, name, declared_sha):
    if Path(name).name != name or name.startswith('.'):
        raise ValueError('Source path must be a direct attempt child')
    path = attempt / name
    if not path.is_file():
        raise ValueError('Original source missing: ' + name)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != declared_sha:
        raise ValueError('Original source hash differs: ' + name)
    return path


def finalize(attempt_dir, review_manifest_path):
    attempt = Path(attempt_dir).resolve()
    manifest_path = Path(review_manifest_path).resolve()
    if manifest_path.parent != attempt:
        raise ValueError('Review manifest must reside in the attempt')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('source_kind') != 'original_native':
        raise ValueError('Original-source manifest required')
    if manifest.get('legal_verdict') is not None:
        raise ValueError('Legal verdict is outside this finalizer')
    declared = manifest.get('sha256')
    if not isinstance(declared, dict):
        raise ValueError('Source hash map missing')
    expected = set(REVIEW_FILES + SOURCE_FILES)
    if set(declared) != expected:
        raise ValueError('Exact Native, camera and review source set required')
    sources = {name: _source(attempt, name, declared[name])
               for name in REVIEW_FILES + SOURCE_FILES}
    for name in REVIEW_FILES:
        review = json.loads(sources[name].read_text())
        if (review.get('source_kind') != 'original_native' or
                review.get('review_status') != 'verified' or
                not review.get('source_basis') or
                review.get('legal_verdict') is not None):
            raise ValueError('Source review is absent or still pending: ' + name)
    native = _rows(sources['native-rows.jsonl'])
    frames = _rows(sources['video_frames.jsonl'])
    observations = _rows(sources['observed-activity.jsonl'])
    if not all(len(rows) == FRAMES for rows in (native, frames, observations)):
        raise ValueError('Full original frame set required')
    measured_rows = []
    for index, (n, f, o) in enumerate(zip(native, frames, observations)):
        if (n.get('video_frame') != index or f.get('video_frame') != index or
                o.get('video_frame') != index or
                n.get('native_frame') != f.get('native_frame') or
                o.get('native_frame') != f.get('native_frame') or
                n.get('time_s') != f.get('time_s') or
                o.get('time_s') != f.get('time_s') or
                not isinstance(n.get('taxi_actor_id'), int) or
                not isinstance(n.get('participant_actor_id'), int)):
            raise ValueError('Native, camera and reviewed frame identities differ')
        camera_frames = f.get('camera_native_frames')
        if not isinstance(camera_frames, dict) or set(camera_frames) != set(VIEWS):
            raise ValueError('Four original camera frame identities required')
        if n.get('source_cameras') != camera_frames or any(
                frame != n['native_frame'] for frame in camera_frames.values()):
            raise ValueError('Original camera frame join differs')
        observed = {key: o.get(key) for key in (
            'observed_taxi_identity', 'observed_stand_location',
            'observed_speed_mps', 'observed_door_open',
            'observed_occupant_count', 'observed_activity')}
        measured_rows.append({'frame': index, 'time_s': (index + 1) / 20,
            'source_kind': 'original_native', **observed,
            'original_source': {
                'native_capture_path': 'native-rows.jsonl',
                'native_capture_sha256': declared['native-rows.jsonl'],
                'participant_review_path': 'participant-activity-review.json',
                'participant_review_sha256': declared['participant-activity-review.json'],
                'designation_review_path': 'stand-designation-review.json',
                'designation_review_sha256': declared['stand-designation-review.json'],
                'other_regulations_review_path': 'other-regulations-review.json',
                'other_regulations_review_sha256': declared['other-regulations-review.json']}})
    result = measure(measured_rows, 'original_native')
    result['source_sha256'] = declared
    result['review_manifest_sha256'] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    result['legal_verdict'] = None
    if manifest.get('synthetic_cpu_fixture') is True:
        result['original_native_observed'] = False
        result['source_kind'] = 'synthetic_cpu_fixture'
    return result
