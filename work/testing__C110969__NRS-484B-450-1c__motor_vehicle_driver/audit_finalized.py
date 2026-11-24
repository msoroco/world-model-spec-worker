"""Independent saved-result/source join for one intersection capture.

This audit checks recorded provenance and measured fields. It does not decide
whether a stop was legally necessary or physically accepted.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from intersection_observables import SourceError, _require, load_source, footprint_intersects_boundary
from native_media import audit_saved_acquisition


def audit(attempt: Path, finalized: Path, case_id: str) -> dict:
    attempt, finalized = Path(attempt), Path(finalized)
    manifest_path = attempt / 'source-manifest.json'
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    result_raw = finalized.read_bytes()
    result = json.loads(result_raw)
    _require(manifest.get('case_id') == case_id == result.get('case_id'),
             'saved/finalized exact case differs')
    _require(result.get('source_manifest_sha256') == hashlib.sha256(manifest_raw).hexdigest(),
             'finalized source-manifest seal differs')
    _require(result.get('native_run_id') == manifest.get('native_run_id'),
             'finalized Native run differs')
    packets = {}
    for name in ('boundary', 'trace', 'activity'):
        ref = manifest.get(name, {})
        path = (attempt / ref.get('path', '')).resolve()
        _require(path.is_relative_to(attempt.resolve()) and path.is_file(),
                 'saved original source missing or escapes attempt: ' + name)
        packets[name] = load_source(path, ref.get('sha256', ''))
        _require(result.get('source_seals', {}).get(name) == ref.get('sha256'),
                 'finalized original source seal differs: ' + name)
    trace = packets['trace'].get('samples', [])
    activity = packets['activity'].get('activity_samples', [])
    observations = result.get('observations', {})
    frames = observations.get('frames', [])
    observed_activity = observations.get('activity_samples', [])
    _require(len(trace) == len(activity) == len(frames) == len(observed_activity) == 900,
             'complete original/finalized 900-frame join required')
    _require(packets['trace'].get('fps') == 20 and result.get('frame_count') == 900,
             'original 20 Hz or finalized frame count differs')
    _require(packets['trace'].get('map_id') == packets['boundary'].get('map_id') == observations.get('map_id'),
             'reviewed map identity differs')
    boundary = packets['boundary'].get('intersection_polygon', [])
    previous = None
    for source_frame, context, row, saved_context in zip(trace, activity, frames, observed_activity):
        frame = source_frame.get('frame')
        _require(isinstance(frame, int) and (previous is None or frame == previous + 1) and
                 frame == context.get('frame') == row.get('frame') == saved_context.get('frame'),
                 'original/finalized frame join differs')
        previous = frame
        _require(context.get('source_ref') and context == saved_context,
                 'independent original activity sample differs')
        _require(row.get('speed_mps') == source_frame.get('speed_mps') and
                 row.get('within_or_touching_boundary') == footprint_intersects_boundary(
                     source_frame.get('body_footprint', []), boundary),
                 'finalized motion or boundary measurement differs')
    for key in ('activity_observation', 'traffic_conflict_observation',
                'law_direction_observation', 'officer_direction_observation',
                'device_direction_observation'):
        _require(observations.get(key) == packets['activity'].get(key),
                 'finalized independent activity/context differs: ' + key)
    media = audit_saved_acquisition(attempt)
    _require(media['case_id'] == case_id and media['native_run_id'] == manifest['native_run_id'] and
             media['media_manifest_sha256'] == manifest.get('media', {}).get('sha256') and
             media['frame_count'] == 900 and media['decoded_camera_frames'] == 3600 and
             result.get('decoded_camera_frames') == 3600,
             'saved four-camera source join differs')
    _require(result.get('physical_completion_verified') is False and
             result.get('legal_conclusion') is None,
             'unreviewed physical or legal claim')
    return {'format': 'worker-intersection-independent-cpu-audit-v1',
            'case_id': case_id, 'native_run_id': manifest['native_run_id'],
            'source_manifest_sha256': hashlib.sha256(manifest_raw).hexdigest(),
            'finalized_sha256': hashlib.sha256(result_raw).hexdigest(),
            'frames_joined': 900, 'camera_frames_decoded': 3600,
            'physical_completion_verified': False, 'legal_conclusion': None}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--finalized', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise SourceError('retain prior audit output; choose a fresh path')
    output.write_text(json.dumps(audit(Path(args.attempt), Path(args.finalized), args.case),
                                 indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
