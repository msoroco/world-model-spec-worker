"""Saved-only C109171 observation and four-camera receipt join.

This code never interprets a WALK indication as statutory permission.
"""
from __future__ import annotations

import json
from pathlib import Path

from native_capture import audit_frame_map
from native_scene import SourceError
from saved_measurement import ASSIGNMENT, EXPECTED, measure_saved


def process(attempt, site_ref, events_ref, frame_map_ref, case_id, output,
            *, expected_frames=600):
    if case_id not in {ASSIGNMENT + '__' + suffix for suffix in EXPECTED}:
        raise SourceError('unknown exact pedestrian case')
    output = Path(output)
    if output.exists():
        raise SourceError('saved process receipt already exists')
    measurement = measure_saved(attempt, site_ref, events_ref, case_id,
                                expected_frames=expected_frames)
    media = audit_frame_map(attempt, frame_map_ref, events_ref,
                            expected_frames=expected_frames)
    if (measurement['frame_count'] != media['frames_audited'] or
            measurement['original_events_sha256'] != events_ref['sha256'] or
            measurement['original_site_sha256'] != site_ref['sha256'] or
            media['camera_frames_audited'] != 4 * expected_frames):
        raise SourceError('saved event and original camera audit differ')
    result = {
        'format': 'c109171-saved-process-v1',
        'case_id': case_id,
        'site_source_sha256': site_ref['sha256'],
        'events_source_sha256': events_ref['sha256'],
        'frame_map_source_sha256': frame_map_ref['sha256'],
        'measurement': measurement,
        'media_audit': media,
        'physical_acceptance': False,
        'statutory_permission': 'unresolved',
        'legal_verdict': None,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n',
                      encoding='utf-8')
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--site-ref', required=True)
    parser.add_argument('--events-ref', required=True)
    parser.add_argument('--frame-map-ref', required=True)
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    refs = [json.loads(Path(value).read_text(encoding='utf-8')) for value in
            (args.site_ref, args.events_ref, args.frame_map_ref)]
    print(json.dumps(process(args.attempt, *refs, args.case_id, args.output),
                     sort_keys=True))


if __name__ == '__main__':
    main()
