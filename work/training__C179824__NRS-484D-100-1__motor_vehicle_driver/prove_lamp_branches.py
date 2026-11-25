"""Synthetic shape checks for source-bound statutory trigger measurements."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json

from lamp_branch_measure import measure, measure_original


def enc(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def jsonl(rows):
    return (''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows)).encode()


def sample():
    sources = {
        'civil_time': {'kind': 'civil_time', 'location': 'Nevada diagnostic location',
                       'ephemeris_source': 'synthetic ephemeris shape',
                       'date_source': 'synthetic clock shape',
                       'sunset': '2026-11-25T18:00:00-08:00',
                       'next_sunrise': '2026-11-26T06:00:00-08:00'},
        'visibility': {'kind': 'visibility', 'method': 'two source observations at 304.8 m',
                       'original_frame_source': 'synthetic frame rows',
                       'observer_source': 'synthetic lane observer'},
        'road_and_class': {'kind': 'road_and_class', 'state': 'Nevada',
                           'public_highway': True, 'highway_source': 'synthetic route shape',
                           'vehicle_class_source': 'synthetic actor class'},
        'parking': {'kind': 'parking', 'original_frame_source': 'synthetic frame rows',
                    'vehicle_motion_source': 'synthetic vehicle motion'},
    }
    raw = {name: enc(value) for name, value in sources.items()}
    start = datetime(2026, 11, 25, 18, 29, 45, tzinfo=timezone(timedelta(hours=-8)))
    frames = []
    for index in range(600):
        native = 800 + index
        frames.append({'video_frame': index, 'native_frame': native,
                       'time_s': index / 20,
                       'camera_native_frames': {name:native for name in
                           ('overview','approach','reference_corner','driver_reference')},
                       'civil_time': (start + timedelta(seconds=index / 20)).isoformat(),
                       'visibility_1000ft': {'native_frame': native, 'distance_m': 304.8,
                                             'person_discernible': index < 200,
                                             'vehicle_discernible': True},
                       'parked': index >= 500,
                       'headlamp_setting_on': True,
                       'position_lamp_setting_on': True})
    packet = {'kind': 'lamp_observations', 'source_kind': 'synthetic_native_sample',
              'source_sha256': {name: hashlib.sha256(value).hexdigest()
                                for name, value in raw.items()}, 'frames': frames}
    return packet, raw


def rejection(packet, sources, error):
    try:
        measure(enc(packet), sources)
    except ValueError as exc:
        if str(exc) != error:
            raise
    else:
        raise AssertionError('accepted invalid source: ' + error)


def replace_source(packet, sources, name, changes):
    record = json.loads(sources[name])
    record.update(changes)
    sources[name] = enc(record)
    packet['source_sha256'][name] = hashlib.sha256(sources[name]).hexdigest()


def main():
    packet, sources = sample()
    result = measure(enc(packet), sources)
    rows = result['frames']
    assert not rows[299]['night_trigger'] and rows[300]['night_trigger']
    assert not rows[199]['visibility_trigger'] and rows[200]['visibility_trigger']
    assert not rows[300]['visibility_trigger']
    assert not rows[499]['parked_exception_review_required']
    assert rows[500]['parked_exception_review_required']
    assert result['class_equipment_sufficiency'] is None
    assert result['parked_exception_disposition'] is None
    trace = jsonl(packet['frames'])
    mapping = jsonl([{'video_frame':row['video_frame'],
                      'native_frame':row['native_frame'],
                      'time_s':row['time_s'],
                      'camera_native_frames':row['camera_native_frames']}
                     for row in packet['frames']])
    original = measure_original(trace, mapping, sources)
    assert original['original_trace_sha256'] == hashlib.sha256(trace).hexdigest()
    damaged_map = jsonl([{'video_frame':row['video_frame'],
                          'native_frame':row['native_frame'] + (1 if i == 200 else 0),
                          'time_s':row['time_s'],
                          'camera_native_frames':row['camera_native_frames']}
                         for i,row in enumerate(packet['frames'])])
    try:
        measure_original(trace, damaged_map, sources)
    except ValueError as exc:
        assert str(exc) == 'original frame map join mismatch'
    else:
        raise AssertionError('changed original frame map accepted')
    negatives = []
    for name, edit, expected in (
        ('missing_civil_source', lambda p,s: s.pop('civil_time'), 'civil_time source missing'),
        ('stale_civil_source', lambda p,s: s.__setitem__('civil_time', b'{}'),
         'civil_time source kind mismatch'),
        ('changed_civil_hash', lambda p,s: p['source_sha256'].__setitem__('civil_time','0'*64),
         'civil_time source hash mismatch'),
        ('missing_ephemeris', lambda p,s: replace_source(p,s,'civil_time',
          {'ephemeris_source':None}), 'sunset/sunrise source missing'),
        ('wrong_highway', lambda p,s: replace_source(p,s,'road_and_class',
          {'public_highway':False}), 'Nevada highway or class source missing'),
        ('missing_visibility', lambda p,s: p['frames'][200].pop('visibility_1000ft'),
         'original 1000-foot person/vehicle discernibility missing'),
        ('weather_proxy', lambda p,s: p['frames'][200]['visibility_1000ft'].pop('person_discernible'),
         'original 1000-foot person/vehicle discernibility missing'),
        ('parked_unknown', lambda p,s: p['frames'][500].pop('parked'),
         'original parked state missing'),
        ('frame_gap', lambda p,s: p['frames'][250].__setitem__('native_frame',
          p['frames'][249]['native_frame']), 'original frame sequence invalid'),
        ('missing_lamp', lambda p,s: p['frames'][250].pop('headlamp_setting_on'),
         'original lamp setting missing'),
    ):
        p, s = copy.deepcopy(packet), copy.deepcopy(sources)
        edit(p,s)
        rejection(p,s,expected)
        negatives.append(name)
    print(json.dumps({'passed':True, 'frame_count':len(rows),
                      'night_boundary_frames':[299,300],
                      'visibility_boundary_frames':[199,200,300],
                      'parked_review_boundary_frames':[499,500],
                      'negative_checks':negatives + ['changed_original_frame_map'],
                      'physical_or_legal_acceptance_claimed':False}, sort_keys=True))


if __name__ == '__main__':
    main()
