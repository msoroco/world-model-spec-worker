"""Independent right-side pass motion audit over retained actor and frame sources.

The motion outcome is separate from the NRS safety judgment. Synthetic fixtures
exercise the geometry but can never establish physical completion.
"""
import hashlib
import json
from pathlib import Path

import measure_raw


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def geometry(rows, frames):
    """Return observed motion features without making a provenance claim."""
    require(len(rows) == len(frames) == 240, 'Missing synchronized source frames')
    require(all(row.get('frame') == i and frame.get('video_frame') == i and
                row.get('native_frame') == frame.get('native_frame') and
                set(frame.get('views', [])) == set(measure_raw.VIEWS)
                for i, (row, frame) in enumerate(zip(rows, frames))),
            'Changed four-view Native frame join')
    first = rows[0]['lead']['center_native_xyz_m'][0] - rows[0]['ego']['center_native_xyz_m'][0]
    last = rows[-1]['lead']['center_native_xyz_m'][0] - rows[-1]['ego']['center_native_xyz_m'][0]
    overlap_right = 0
    minimum_gap = None
    for row in rows:
        e, l = row['ego'], row['lead']
        require(e.get('actor_id') != l.get('actor_id') and
                len(e.get('body_native_xyz_m', [])) >= 4 and
                len(l.get('body_native_xyz_m', [])) >= 4,
                'Missing distinct actor bodies')
        ego_x = measure_raw.project(measure_raw.hull(e['body_native_xyz_m']), (1, 0))
        lead_x = measure_raw.project(measure_raw.hull(l['body_native_xyz_m']), (1, 0))
        overlap = ego_x[1] >= lead_x[0] and lead_x[1] >= ego_x[0]
        right = e['center_native_xyz_m'][1] < l['center_native_xyz_m'][1]
        if overlap and right:
            overlap_right += 1
            gap = measure_raw.footprint_gap(e['body_native_xyz_m'], l['body_native_xyz_m'])
            minimum_gap = gap if minimum_gap is None else min(minimum_gap, gap)
    return {'initial_lead_ahead_m': first, 'final_lead_ahead_m': last,
            'right_overlap_frames': overlap_right, 'minimum_body_gap_m': minimum_gap,
            'complete_motion_observed': first > 0 and last < 0 and overlap_right > 0 and
                                        minimum_gap is not None and minimum_gap > 0}


def audit(folder):
    folder = Path(folder)
    paths = {name: folder/name for name in ('native-raw-actors.jsonl', 'video_frames.jsonl',
                                             'native-map-readback.json', 'capture/evidence.jsonl')}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        return {'status': 'unverified', 'method': 'retained-source right-pass motion audit',
                'sources': {name: sha(path) for name, path in paths.items() if path.is_file()},
                'missing_evidence': missing, 'maneuver_completed': False,
                'legal_safety_verdict': None}
    rows = measure_raw.read_jsonl(paths['native-raw-actors.jsonl'])
    frames = measure_raw.read_jsonl(paths['video_frames.jsonl'])
    mapping = json.loads(paths['native-map-readback.json'].read_text())
    require(rows and mapping.get('source_kind') == rows[0].get('source_kind') and
            {row.get('source_kind') for row in rows} in
            ({'original_native'}, {'synthetic_native_sample'}),
            'Mixed or unbound Native provenance')
    features = geometry(rows, frames)
    source_kind = rows[0]['source_kind']
    status = ('unverified' if source_kind == 'synthetic_native_sample' else
              'met' if features['complete_motion_observed'] else 'not_met')
    return {'status': status, 'method': 'source-derived body overlap and longitudinal order',
            'sources': {name: sha(path) for name, path in paths.items()},
            'source_kind': source_kind, 'features': features,
            'missing_evidence': ['original Native motion'] if status == 'unverified' else [],
            'maneuver_completed': status == 'met', 'legal_safety_verdict': None}


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('folder', type=Path)
    args = p.parse_args()
    print(json.dumps(audit(args.folder), sort_keys=True))
