"""Saved-only source join for a proposed original flagger Native attempt.

This measures motorcycle motion against the requested signal schedule. It does
not decide whether an authorized, visible, governing flagger gave that signal.
"""

import hashlib
import json
import math
from pathlib import Path


CAMERAS = ('overview', 'approach', 'flagger', 'rear')
REVIEW_COPIES = {
    'authority_source_sha256': 'original-authority-source',
    'zone_designation_source_sha256': 'original-zone-source',
    'signal_asset_source_sha256': 'original-signal-source',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(attempt, case_id):
    attempt = Path(attempt)
    suffix = case_id.rsplit('__', 1)[-1]
    if suffix not in ('probe_a', 'probe_b', 'probe_c', 'probe_d'):
        raise ValueError('Unknown exact flagger case')
    location_basis = ('clearly_marked_construction_or_maintenance_area'
                      if suffix in ('probe_c', 'probe_d') else
                      'designated_temporary_zone')
    manifest = json.loads((attempt / 'captured-source-hashes.json').read_text())
    required = {'road.xodr', 'native-rows.jsonl', 'video_frames.jsonl',
                'original-flagger-review.json'} | set(REVIEW_COPIES.values()) | {
                name + '.mkv' for name in CAMERAS}
    if (manifest.get('source_kind') != 'original_native_capture' or
            manifest.get('case_id') != case_id or
            manifest.get('original_signal_pixels_reviewed') is not False or
            manifest.get('physical_or_legal_outcome_claimed') is not False or
            set(manifest.get('sha256', {})) != required):
        raise ValueError('Original Native source seal differs')
    for name, expected in manifest['sha256'].items():
        if not (attempt / name).is_file() or sha(attempt / name) != expected:
            raise ValueError('Original Native source missing or changed: ' + name)
    review = json.loads((attempt / 'original-flagger-review.json').read_text())
    if review.get('statutory_location_basis') != location_basis:
        raise ValueError('Original flagger statutory location source binding differs')
    for key, name in REVIEW_COPIES.items():
        if review.get(key) != manifest['sha256'][name]:
            raise ValueError('Original flagger review source binding differs: ' + name)
    if review.get('governs_approach') is not True:
        raise ValueError('Original flagger governance packet missing')
    rows = [json.loads(line) for line in
            (attempt / 'native-rows.jsonl').read_text().splitlines()]
    frame_map = [json.loads(line) for line in
                 (attempt / 'video_frames.jsonl').read_text().splitlines()]
    if len(rows) != 600 or len(frame_map) != 600:
        raise ValueError('Original Native frame coverage incomplete')
    first_frame = rows[0]['native_frame']
    first_cross = None
    first_body_cross = None
    indication_at_cross = None
    stop_seen = release_seen = False
    stopped_frames_during_stop = 0
    body_crossed_during_stop = False
    actor_ids = None
    location_actor_ids = None
    work_area_expected = case_id.endswith(('__probe_c', '__probe_d'))
    for index, (row, mapping) in enumerate(zip(rows, frame_map)):
        frame = first_frame + index
        identities = (row.get('motorcycle_actor_id'), row.get('flagger_actor_id'))
        if (row.get('source_kind') != 'original_native' or
                row.get('video_frame') != index or
                row.get('native_frame') != frame or
                mapping.get('video_frame') != index or
                mapping.get('native_frame') != frame or
                not isinstance(row.get('time_s'), (int, float)) or
                not math.isfinite(row['time_s']) or
                not isinstance(mapping.get('time_s'), (int, float)) or
                not math.isfinite(mapping['time_s']) or
                abs(row.get('time_s', -1) - (index + 1) / 20) > .001 or
                abs(mapping.get('time_s', -1) - row['time_s']) > .001 or
                row.get('source_cameras') != {name: frame for name in CAMERAS} or
                mapping.get('camera_native_frames') != row['source_cameras'] or
                row.get('motorcycle_blueprint') != 'vehicle.kawasaki.ninja' or
                not isinstance(row.get('motorcycle_actor_id'), int) or
                not isinstance(row.get('flagger_actor_id'), int)):
            raise ValueError('Original motorcycle, flagger or camera frame join differs')
        if actor_ids is None:
            actor_ids = identities
        elif identities != actor_ids:
            raise ValueError('Original motorcycle or flagger actor identity changed')
        location_ids = (row.get('zone_entry_marker_actor_id'),
                        row.get('zone_exit_marker_actor_id'),
                        row.get('stop_signal_actor_id'),
                        row.get('release_signal_actor_id'))
        work_ids = row.get('work_area_actor_ids')
        if (any(type(value) is not int for value in location_ids) or
                not isinstance(work_ids, list) or
                len(work_ids) != (3 if work_area_expected else 0) or
                any(type(value) is not int for value in work_ids) or
                len(set((*identities, *location_ids, *work_ids))) !=
                2 + len(location_ids) + len(work_ids)):
            raise ValueError('Original location or signal actor identity missing')
        combined = (*location_ids, *work_ids)
        if location_actor_ids is None:
            location_actor_ids = combined
        elif combined != location_actor_ids:
            raise ValueError('Original location or signal actor identity changed')
        xyz = row.get('motorcycle_xyz_m')
        body = row.get('motorcycle_body_vertices_m')
        if (not isinstance(xyz, list) or len(xyz) != 3 or
                any(not isinstance(v, (int, float)) or not math.isfinite(v)
                    for v in xyz) or
                not isinstance(body, list) or len(body) != 8 or
                any(not isinstance(vertex, list) or len(vertex) != 3 or
                    any(not isinstance(v, (int, float)) or not math.isfinite(v)
                        for v in vertex)
                    for vertex in body) or
                not isinstance(row.get('motorcycle_speed_mps'), (int, float)) or
                not math.isfinite(row['motorcycle_speed_mps']) or
                row['motorcycle_speed_mps'] < 0 or
                abs(xyz[1] + 1.75) > 1.5):
            raise ValueError('Original supported motorcycle lane or motion missing')
        if (min(v[0] for v in body) > xyz[0] or
                max(v[0] for v in body) < xyz[0] or
                min(v[1] for v in body) > xyz[1] or
                max(v[1] for v in body) < xyz[1]):
            raise ValueError('Original motorcycle body does not surround actor')
        requested = row.get('requested_signal')
        if requested != ('stop' if 100 <= index < 300 else 'release'):
            raise ValueError('Requested flagger signal schedule differs')
        stop_seen |= requested == 'stop'
        release_seen |= requested == 'release' and stop_seen
        if requested == 'stop' and row['motorcycle_speed_mps'] <= .1:
            stopped_frames_during_stop += 1
        if max(v[0] for v in body) >= 0:
            if requested == 'stop':
                body_crossed_during_stop = True
            if first_body_cross is None:
                first_body_cross = frame
        if first_cross is None and xyz[0] >= 0:
            first_cross = frame
            indication_at_cross = requested
    if not stop_seen or not release_seen or first_cross is None or first_body_cross is None:
        raise ValueError('Original stop, release or crossing event missing')
    return {'case_id': case_id, 'source_kind': 'original_native_capture',
            'statutory_location_basis': location_basis,
            'source_seal_sha256': sha(attempt / 'captured-source-hashes.json'),
            'frame_count': 600, 'rate_hz': 20,
            'zone_marker_actor_ids': list(location_actor_ids[:2]),
            'work_area_actor_ids': list(location_actor_ids[4:]),
            'first_observed_stop_line_cross_frame': first_cross,
            'first_observed_body_stop_line_cross_frame': first_body_cross,
            'observed_stopped_frames_during_requested_stop': stopped_frames_during_stop,
            'body_crossed_during_requested_stop': body_crossed_during_stop,
            'requested_indication_at_crossing': indication_at_cross,
            'original_signal_pixels_reviewed': False,
            'flagger_authority_verified': False,
            'zone_designation_verified': False,
            'physical_completion': None,
            'legal_verdict': None}
