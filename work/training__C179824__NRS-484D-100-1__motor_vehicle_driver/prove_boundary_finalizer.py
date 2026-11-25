"""CPU predicate proof for the source-bound boundary finalizer."""
from datetime import datetime, timedelta
import hashlib
import json

from native.finalize_boundary import reviewed_measure
from visibility_measure import CAMERAS


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'))+'\n' for row in rows).encode()


def packet(distance_ft=1000, civil_branch='sunset', civil_offset_min=30):
    road = b'<OpenDRIVE/>'
    distance = distance_ft*.3048
    frame_map = []
    trace = []
    for i in range(600):
        joint = {name: i+1000 for name in CAMERAS}
        frame_map.append({'video_frame': i, 'native_frame': i+1000,
                          'carla_frame': i+1000, 'time_s': i/20,
                          'camera_native_frames': joint})
        trace.append({'video_frame': i, 'native_frame': i+1000,
                      'time_s': i/20, 'ego_speed_mps': 2.0,
                      'ego_light_state_bits': 3,
                      'camera_native_frames': joint,
                      'ego_xy_m': [-200+i*.1, -1.75],
                      'person_forward_distance_m': distance if i == 0 else distance-i*.1,
                      'vehicle_forward_distance_m': distance if i == 0 else distance-i*.1})
    raw = {'road.xodr': road,
           'video_frames.jsonl': lines(frame_map),
           'visibility-trace.jsonl': lines(trace),
           'sun-event-source.json': b'{"source_kind":"dated_sun_event_source"}',
           'location-source.json': b'{"location":"Nevada source fixture"}'}
    raw.update({name+'.mkv': (name+' diagnostic bytes').encode() for name in CAMERAS})
    raw['visibility-context.json'] = json.dumps({
        'source_kind': 'native_saved_sample', 'map_source_sha256': sha(road),
        'reference_distance_m': distance, 'statutory_reference_distance_m': 304.8,
        'requested_boundary_distance_ft': distance_ft}).encode()
    raw['visibility-pixel-review.json'] = json.dumps({
        'source_kind': 'original_pixel_review', 'reviewer_id': 'cpu-predicate-fixture',
        'trace_sha256': sha(raw['visibility-trace.jsonl']),
        'map_sha256': sha(road),
        'context_sha256': sha(raw['visibility-context.json']),
        'frame_map_sha256': sha(raw['video_frames.jsonl']),
        'person_video': 'overview.mkv',
        'person_video_sha256': sha(raw['overview.mkv']),
        'vehicle_video': 'approach.mkv',
        'vehicle_video_sha256': sha(raw['approach.mkv']),
        'person_review_frames': [0], 'vehicle_review_frames': [0],
        'person_clearly_discernible': True,
        'vehicle_clearly_discernible': False}).encode()
    sunset = datetime.fromisoformat('2026-11-25T16:30:00-08:00')
    sunrise = datetime.fromisoformat('2026-11-26T06:30:00-08:00')
    start = (sunset+timedelta(minutes=civil_offset_min) if civil_branch == 'sunset' else
             sunrise-timedelta(minutes=civil_offset_min) if civil_branch == 'sunrise' else
             sunset+timedelta(hours=1))
    raw['civil-clock.json'] = json.dumps({
        'source_kind': 'native_saved_sample',
        'frame_times': [(start+timedelta(seconds=i/20)).isoformat()
                        for i in range(600)]}).encode()
    for i, item in enumerate(trace):
        item['civil_time_iso'] = (start+timedelta(seconds=i/20)).isoformat()
    raw['visibility-trace.jsonl'] = lines(trace)
    pixel = json.loads(raw['visibility-pixel-review.json'])
    pixel['trace_sha256'] = sha(raw['visibility-trace.jsonl'])
    raw['visibility-pixel-review.json'] = json.dumps(pixel).encode()
    raw['civil-time-review.json'] = json.dumps({
        'source_kind': 'independent_civil_time_review',
        'clock_sha256': sha(raw['civil-clock.json']),
        'reviewer_id': 'cpu-predicate-fixture',
        'sun_event_source': 'diagnostic fixture',
        'sun_event_source_sha256': sha(raw['sun-event-source.json']),
        'location_source': 'diagnostic fixture',
        'location_source_sha256': sha(raw['location-source.json']),
        'applicable_sunset': sunset.isoformat(),
        'following_sunrise': sunrise.isoformat()}).encode()
    return raw


def expect_failure(raw, phrase):
    try:
        reviewed_measure(raw)
    except ValueError as error:
        if phrase not in str(error):
            raise
        return
    raise AssertionError('source omission unexpectedly passed')


def main():
    raw = packet()
    measured = reviewed_measure(raw)
    if len(measured['civil_time']['trigger_frames']) != 600:
        raise AssertionError('30-minute sunset boundary did not activate')
    if 0 not in measured['visibility']['person_source_frames'] or 0 not in measured['visibility']['vehicle_source_frames']:
        raise AssertionError('joint 1,000-foot reference omitted')
    changed = dict(raw)
    changed['overview.mkv'] = b'stale video'
    expect_failure(changed, 'Original person video hash changed')
    changed = dict(raw)
    changed.pop('sun-event-source.json')
    try:
        reviewed_measure(changed)
    except KeyError:
        pass
    else:
        raise AssertionError('sun-event source omission unexpectedly passed')
    print(json.dumps({'passed': True, 'positive': 1, 'negative': 2,
                      'diagnostic_fixture': True,
                      'original_capture_attested': False}, sort_keys=True))


if __name__ == '__main__':
    main()
