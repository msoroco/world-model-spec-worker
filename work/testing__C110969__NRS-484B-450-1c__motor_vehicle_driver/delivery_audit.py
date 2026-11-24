"""Independent exact-case source and media audit; no statutory acceptance inference."""
import hashlib
import json
from pathlib import Path

from finalize_observables import finalize


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(attempt, case_id, *, allow_diagnostic=False):
    from worker_exchange.media import audit as audit_video

    attempt = Path(attempt).resolve()
    source = attempt / 'diagnostic-manifest.json'
    diagnostic = source.is_file()
    if diagnostic and not allow_diagnostic:
        raise ValueError('diagnostic fixture cannot establish delivery acceptance')
    if not diagnostic:
        source = attempt / 'source-manifest.json'
    if not source.is_file():
        raise ValueError('original source manifest missing')
    observations = finalize(source)
    if observations['case_id'] != case_id:
        raise ValueError('exact case identity differs')
    frames = observations['frames']
    if not diagnostic and len(frames) != 900:
        raise ValueError('full original 900-frame interval missing')
    if not frames:
        raise ValueError('original frames missing')
    trace_rows = [json.loads(row) for row in (attempt/'trace.jsonl').read_text().splitlines()]
    mapping = [json.loads(row) for row in (attempt/'video_frames.jsonl').read_text().splitlines()]
    if (len(frames) != len(trace_rows) or len(frames) != len(mapping)
            or any(frame['frame'] != row['frame'] or row['frame'] != media['carla_frame']
                   or abs(row['time_s']-media['time_s']) > 1e-6
                   for frame, row, media in zip(frames, trace_rows, mapping))):
        raise ValueError('original frame and media map join differs')
    videos = {}
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        path = attempt/(name+'.mkv')
        decoded = audit_video(path, len(frames), mapping_sha256=sha(attempt/'video_frames.jsonl'))
        if decoded.get('passed') is not True:
            raise ValueError('original video decode incomplete: '+name)
        videos[name] = {'sha256': sha(path), 'decoded_frames': decoded['frames']}
    return {'format': 'intersection-independent-delivery-audit-v1', 'case_id': case_id,
            'diagnostic_fixture': diagnostic, 'source_manifest_sha256': sha(source),
            'original_frame_count': len(frames), 'source_seals': observations['source_seals'],
            'videos': videos, 'source_join_verified': True,
            'physical_completion': 'unverified', 'legal_conclusion': None,
            'canonical_delivery_acceptance': 'unverified'}
