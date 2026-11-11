"""Independent original-source and four-camera audit for overtaking attempts."""

from hashlib import sha256
import json
from pathlib import Path

from overtake_finalizer import analyze

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('participant_footprints.jsonl', 'video_frames.jsonl', 'trace.jsonl')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit_attempt(attempt, report, *, decoder=None):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    for name in (*SOURCES, 'config.json'):
        if not (root / name).is_file():
            raise ValueError('Missing audited original overtaking source: ' + name)
    sources = report['measurements']['overtake_observation']['sources']
    if set(sources) != set(SOURCES):
        raise ValueError('Overtaking analysis source inventory differs')
    if any(digest(root / name) != expected for name, expected in sources.items()):
        raise ValueError('Overtaking analysis original source hash differs')
    independent = analyze(root)
    if (independent['case_id'] != report['case_id'] or
            independent['measurements'] != report['measurements']):
        raise ValueError('Overtaking analysis differs from independently recomputed originals')
    mapping = [json.loads(line) for line in (root / 'video_frames.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (root / 'trace.jsonl').read_text().splitlines()]
    if not mapping or len(trace) != len(mapping):
        raise ValueError('Original overtaking frame map or trace incomplete')
    if any((m.get('carla_frame'), m.get('time_s')) != (t.get('frame'), t.get('time_s'))
           for m, t in zip(mapping, trace)):
        raise ValueError('Original overtaking trace/frame join differs')
    if decoder is None:
        from worker_exchange.media import audit as decoder
    cameras = {}
    for name in CAMERAS:
        source = root / (name + '.mkv')
        if not source.is_file():
            raise ValueError('Missing named overtaking source camera: ' + name)
        decoded = decoder(source, len(mapping), mapping_sha256=digest(root / 'video_frames.jsonl'))
        if decoded.get('frames') != len(mapping):
            raise ValueError('Overtaking source camera frame count differs: ' + name)
        cameras[name] = {'source_sha256': digest(source), 'decode': decoded}
    return {'format': 'worker-overtake-source-audit', 'case_id': report['case_id'],
            'source_hashes': sources, 'frame_count': len(mapping),
            'camera_decodes': cameras, 'measurement_recomputed': True,
            'physical_visibility_claimed': False, 'legal_acceptance_claimed': False}
