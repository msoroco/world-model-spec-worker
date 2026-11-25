"""Independent saved-attempt audit; no CARLA or legal conclusion."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


class DeliveryError(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise DeliveryError(message)


def sealed(root, ref):
    base = Path(root).resolve()
    path = (base / ref['path']).resolve()
    need(path.is_relative_to(base) and path.is_file(), 'missing or escaping source')
    need(hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'], 'source hash mismatch')
    return path


def audit_saved(root, manifest):
    """Fail closed on missing or discontinuous original source evidence.

    Manifest packet comes from an attempt directory, not the authored case plan.
    Camera metadata is a source-bound acquisition inventory; physical readability
    still needs pixel review of the actual encoded sources.
    """
    need(manifest.get('case_id') and manifest.get('assignment_id'), 'case binding missing')
    need(manifest.get('law_id') == 'NRS-484B-307-9b', 'law binding mismatch')
    need(manifest.get('actor') == 'motorcycle_or_moped_operator', 'actor binding mismatch')
    need(manifest.get('fps') == 20, 'capture rate mismatch')
    need(manifest.get('duration_frames') == 900, 'exact 45 second history missing')
    source_refs = manifest.get('sources')
    need(isinstance(source_refs, dict), 'source inventory missing')
    for key in ('original_events', 'map', 'route', 'signal', 'stop_reference', 'crosswalk'):
        need(key in source_refs, 'missing source: ' + key)
        sealed(root, source_refs[key])
    if manifest['case_id'].endswith('__no_causal_record'):
        need('cause' not in source_refs and manifest.get('cause_status') == 'not_established',
             'negative causal case must retain absence of affirmative source')
    else:
        need('cause' in source_refs, 'missing source: cause')
        sealed(root, source_refs['cause'])
    rows = json.loads(sealed(root, source_refs['original_events']).read_text())
    need(isinstance(rows, list) and len(rows) == manifest['duration_frames'], 'original frame count mismatch')
    frames = [r.get('frame') for r in rows]
    need(all(isinstance(f, int) for f in frames) and frames == list(range(frames[0], frames[0] + len(frames))), 'original frame discontinuity')
    need(all(r.get('official_head_id') == manifest.get('official_head_id') for r in rows), 'governing head drift')
    need(all(r.get('actor_id') == manifest.get('actor_id') for r in rows), 'ego actor drift')
    views = manifest.get('camera_views')
    need(isinstance(views, dict) and set(views) == set(VIEWS), 'four-view capture missing')
    source_paths = [views[name]['source']['path'] for name in VIEWS]
    need(len(set(source_paths)) == len(source_paths), 'four-view sources must be distinct')
    for name in VIEWS:
        view = views[name]
        sealed(root, view['source'])
        need(view.get('decoded_frames') == len(rows), 'decoded frame count mismatch: ' + name)
        need(view.get('fps') == 20, 'camera rate mismatch: ' + name)
        need(view.get('width', 0) > 0 and view.get('height', 0) > 0, 'camera dimensions missing: ' + name)
        need(view.get('first_original_frame') == frames[0] and view.get('last_original_frame') == frames[-1], 'camera alignment mismatch: ' + name)
    need(manifest.get('pixel_review_status') in ('pending', 'passed'), 'pixel review status absent')
    return {'case_id': manifest['case_id'], 'original_frames': len(rows),
            'camera_views_checked': list(VIEWS), 'source_seals_checked': len(source_refs)+len(VIEWS),
            'physical_acceptance': False, 'legal_verdict': None}
