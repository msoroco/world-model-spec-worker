"""Source-bound half-hour sunset and sunrise lamp trigger measurement."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def moment(value):
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None,
            'Civil time requires offset-aware source timestamps')
    return parsed


def measure(clock_raw, review_raw):
    clock = json.loads(clock_raw)
    review = json.loads(review_raw)
    kind = clock.get('source_kind')
    require(kind in ('native_saved_sample', 'synthetic_diagnostic') and
            isinstance(clock.get('frame_times'), list) and
            len(clock['frame_times']) == 600,
            'Original 600-frame civil-time source missing')
    require(review.get('source_kind') == ('independent_civil_time_review' if
            kind == 'native_saved_sample' else 'synthetic_diagnostic') and
            review.get('clock_sha256') == digest(clock_raw) and
            review.get('reviewer_id') and review.get('sun_event_source') and
            review.get('sun_event_source_sha256') and review.get('location_source') and
            review.get('location_source_sha256'),
            'Independent dated and located sun-event source missing')
    sunset = moment(review['applicable_sunset'])
    sunrise = moment(review['following_sunrise'])
    require(sunset < sunrise and sunrise - sunset < timedelta(days=2),
            'Sunset/sunrise source order invalid')
    begin = sunset + timedelta(minutes=30)
    end = sunrise - timedelta(minutes=30)
    require(begin < end, 'Half-hour statutory interval invalid')
    frame_times = [moment(x) for x in clock['frame_times']]
    require(all(a < b for a, b in zip(frame_times, frame_times[1:])),
            'Civil-time frame order missing')
    require(all(t.date() in (sunset.date(), sunrise.date()) for t in frame_times),
            'Civil-time frame outside reviewed sun-event dates')
    return {'format': 'c179824-civil-time-measurement-v1',
            'source_kind': kind,
            'statutory_offset_minutes': 30,
            'interval_start': begin.isoformat(),
            'interval_end': end.isoformat(),
            'trigger_frames': [i for i, t in enumerate(frame_times) if begin <= t <= end],
            'clock_sha256': digest(clock_raw),
            'review_sha256': digest(review_raw),
            'legal_verdict_claimed': False}


def self_test(negative=False):
    sunset = moment('2026-11-25T16:30:00-08:00')
    sunrise = moment('2026-11-26T06:30:00-08:00')
    outcomes = {}
    for branch, minutes, start, expected in (
        ('sunset', 29, sunset+timedelta(minutes=29), 0),
        ('sunset', 30, sunset+timedelta(minutes=30), 600),
        ('sunset', 31, sunset+timedelta(minutes=31), 600),
        ('sunrise', 29, sunrise-timedelta(minutes=29), 0),
        ('sunrise', 30, sunrise-timedelta(minutes=30), 1),
        ('sunrise', 31, sunrise-timedelta(minutes=31), 600)):
        clock = json.dumps({'source_kind': 'native_saved_sample',
                            'frame_times': [(start + timedelta(seconds=i/20)).isoformat()
                                            for i in range(600)]}).encode()
        review = {'source_kind': 'independent_civil_time_review',
                  'clock_sha256': digest(clock), 'reviewer_id': 'cpu-predicate-fixture',
                  'sun_event_source': 'dated official event table fixture',
                  'sun_event_source_sha256': digest(b'event-table'),
                  'location_source': 'geocoded position fixture',
                  'location_source_sha256': digest(b'location'),
                  'applicable_sunset': sunset.isoformat(),
                  'following_sunrise': sunrise.isoformat()}
        if negative:
            review.pop('sun_event_source_sha256')
            return measure(clock, json.dumps(review).encode())
        result = measure(clock, json.dumps(review).encode())
        require(len(result['trigger_frames']) == expected,
                'Half-hour source boundary classified incorrectly')
        outcomes[branch+'_'+str(minutes)] = expected
    return {'format': 'c179824-civil-time-boundary-cpu-proof-v1',
            'diagnostic_fixture': True, 'boundary_trigger_frame_counts': outcomes,
            'original_capture_attested': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--clock')
    parser.add_argument('--review')
    parser.add_argument('--source-root')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(args.negative), indent=2))
    else:
        require(args.clock and args.review and args.output and args.source_root,
                'Original clock, independent review, source root and output required')
        root = Path(args.source_root).resolve()
        source_review = Path(args.review).read_bytes()
        review_data = json.loads(source_review)
        for field in ('sun_event', 'location'):
            rel = review_data.get(field+'_path')
            require(isinstance(rel, str) and rel and not Path(rel).is_absolute(),
                    'Independent '+field+' source path missing')
            path = (root/rel).resolve()
            require(root in path.parents and path.is_file(),
                    'Independent '+field+' source outside saved sources')
            require(digest(path.read_bytes()) == review_data.get(field+'_source_sha256'),
                    'Independent '+field+' source changed')
        result = measure(Path(args.clock).read_bytes(), source_review)
        Path(args.output).write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result, sort_keys=True))
