"""Independent exact-case source and media audit; no statutory acceptance inference."""
import hashlib
import json
from pathlib import Path

from finalize_observables import finalize


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_live_sources(attempt, case_id, frames, videos, mapping):
    provenance = json.loads((attempt/'acquisition-provenance.json').read_text())
    if provenance.get('provenance_kind') != 'native' or provenance.get('diagnostic_fixture') is not False:
        raise ValueError('original Native provenance missing')
    index_path = attempt/'reviewed-source-index.json'
    index = json.loads(index_path.read_text())
    if provenance.get('source_index_sha256') != sha(index_path):
        raise ValueError('original reviewed source index differs')
    if index.get('case_id') != case_id or not index.get('reviewer') or not index.get('review_note'):
        raise ValueError('independent exact source review missing')
    for kind in ('route', 'boundary', 'camera'):
        copy = attempt/('reviewed-'+kind+'.json')
        if sha(copy) != index.get('packet_refs', {}).get(kind, {}).get('sha256'):
            raise ValueError('reviewed source packet differs: '+kind)
    graph_path = attempt/'capture'/'manifest.json'
    graph = json.loads(graph_path.read_text())
    if graph.get('extraction_confirmed') is not True or graph.get('frames') != len(frames):
        raise ValueError('original graph extraction incomplete')
    for name in ('road.xodr','trace.jsonl','carla_recorder.log'):
        if graph.get('sources', {}).get(name) != sha(attempt/name):
            raise ValueError('original graph source differs: '+name)
    evidence = [json.loads(row) for row in (attempt/'capture'/'evidence.jsonl').read_text().splitlines()]
    if (len(evidence) != len(frames) or
            any(row.get('original_frame') != frame['frame'] or
                row.get('replay_frame') != frame['frame'] or
                abs(row.get('recording_time_s', -1)-media['time_s']) > 1e-6
                for row, frame, media in zip(evidence, frames, mapping))):
        raise ValueError('original graph evidence/frame join differs')
    exported = json.loads((attempt/'native-export-receipt.json').read_text())
    if (exported.get('case_id') != case_id or
            exported.get('graph_manifest_sha256') != sha(graph_path) or
            exported.get('trace_sha256') != sha(attempt/'trace.jsonl') or
            exported.get('frame_map_sha256') != sha(attempt/'video_frames.jsonl')):
        raise ValueError('original graph/media export seal differs')
    for name, decoded in videos.items():
        if (exported.get('videos', {}).get(name, {}).get('sha256') != decoded['sha256'] or
                exported['videos'][name].get('rgb_sequence_sha256') != decoded['rgb_sequence_sha256']):
            raise ValueError('original camera pixels differ: '+name)
    seal = json.loads((attempt/'capture-seal.json').read_text())
    if (seal.get('provenance_kind') != 'native' or seal.get('frames') != len(frames) or
            seal.get('restoration', {}).get('restored') is not True or
            seal.get('events') != ['capture_finished','encoders_closed','restoration_verified'] or
            seal.get('source_digest') is None):
        raise ValueError('original Native capture seal incomplete')
    expected_digest = hashlib.sha256(json.dumps(
        seal['sources'], sort_keys=True, separators=(',', ':'),
        ensure_ascii=False).encode()).hexdigest()
    if seal['source_digest'] != expected_digest:
        raise ValueError('original Native source tree digest differs')
    for name, expected in seal['sources'].items():
        path = (attempt/name).resolve()
        if not path.is_relative_to(attempt) or not path.is_file() or sha(path) != expected:
            raise ValueError('original capture source tree differs: '+name)
    for name in ('road.xodr','trace.jsonl','video_frames.jsonl','capture/manifest.json',
                 'capture/evidence.jsonl','native-export-receipt.json'):
        if seal.get('sources', {}).get(name) != sha(attempt/name):
            raise ValueError('original capture source seal differs: '+name)
    review = json.loads((attempt/'physical-review.json').read_text())
    if (review.get('case_id') != case_id or not review.get('reviewer') or
            review.get('physical_completion_verified') is not True or
            review.get('source_sha256', {}).get('capture-seal.json') != sha(attempt/'capture-seal.json') or
            review.get('source_sha256', {}).get('source-manifest.json') != sha(attempt/'source-manifest.json')):
        raise ValueError('independent physical completion review missing')
    return {'graph_manifest_sha256': sha(graph_path),
            'capture_seal_sha256': sha(attempt/'capture-seal.json'),
            'physical_review_sha256': sha(attempt/'physical-review.json')}


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
        videos[name] = {'sha256': sha(path), 'decoded_frames': decoded['frames'],
                        'rgb_sequence_sha256': decoded['rgb_sequence_sha256']}
    live = None if diagnostic else audit_live_sources(attempt, case_id, frames, videos, mapping)
    return {'format': 'intersection-independent-delivery-audit-v1', 'case_id': case_id,
            'diagnostic_fixture': diagnostic, 'source_manifest_sha256': sha(source),
            'original_frame_count': len(frames), 'source_seals': observations['source_seals'],
            'videos': videos, 'source_join_verified': True,
            'original_graph_review': live,
            'physical_completion': 'unverified' if diagnostic else 'independently_reviewed',
            'legal_conclusion': None,
            'canonical_delivery_acceptance': 'unverified' if diagnostic else 'source_verified'}
