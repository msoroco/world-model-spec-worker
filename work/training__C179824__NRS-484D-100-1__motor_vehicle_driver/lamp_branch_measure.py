"""Source-bound activation measurements for NRS 484D.100(1).

This module measures statutory trigger facts and records unresolved facts. It does
not decide class-specific equipment sufficiency or legal compliance.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
import math


def require(condition, message):
    if not condition:
        raise ValueError(message)


def stamp(value):
    require(isinstance(value, str), 'civil timestamp missing')
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('invalid civil timestamp') from exc
    require(result.tzinfo is not None and result.utcoffset() is not None,
            'civil timestamp lacks timezone')
    return result


def source_record(raw, expected_kind):
    require(isinstance(raw, bytes) and bool(raw), expected_kind + ' source missing')
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(expected_kind + ' source invalid') from exc
    require(isinstance(value, dict) and value.get('kind') == expected_kind,
            expected_kind + ' source kind mismatch')
    return value


def measure(raw_observations, sources):
    """Measure a 20 Hz interval using original or explicitly synthetic source bytes.

    Sources are keyed by original channel name; the packet hashes each required
    source. The visibility source records separate person and vehicle observations
    exactly 304.8 m ahead. Weather is context, never a visibility substitute.
    """
    require(isinstance(sources, dict), 'sources missing')
    packet = source_record(raw_observations, 'lamp_observations')
    require(packet.get('source_kind') in ('native_saved_sample', 'synthetic_native_sample'),
            'observation provenance missing')
    required = ('civil_time', 'visibility', 'road_and_class', 'parking')
    decoded = {}
    for name in required:
        raw = sources.get(name)
        value = source_record(raw, name)
        require(packet.get('source_sha256', {}).get(name) == hashlib.sha256(raw).hexdigest(),
                name + ' source hash mismatch')
        decoded[name] = value
    civil, visibility, context, parking = (decoded[name] for name in required)
    require(civil.get('location') and civil.get('ephemeris_source') and
            civil.get('date_source'), 'sunset/sunrise source missing')
    sunset, sunrise = stamp(civil.get('sunset')), stamp(civil.get('next_sunrise'))
    require(sunrise > sunset + timedelta(minutes=60), 'sunrise/sunset order invalid')
    night_begin, night_end = sunset + timedelta(minutes=30), sunrise - timedelta(minutes=30)
    require(context.get('state') == 'Nevada' and context.get('public_highway') is True and
            context.get('highway_source') and context.get('vehicle_class_source'),
            'Nevada highway or class source missing')
    require(visibility.get('method') and visibility.get('original_frame_source') and
            visibility.get('observer_source'), 'discernibility source missing')
    require(parking.get('original_frame_source') and parking.get('vehicle_motion_source'),
            'parking source missing')
    rows = packet.get('frames')
    require(isinstance(rows, list) and len(rows) >= 600, 'recording shorter than 30 seconds')
    measured = []
    last_native = None
    for index, row in enumerate(rows):
        native = row.get('native_frame')
        require(row.get('video_frame') == index and type(native) is int and
                (last_native is None or native > last_native), 'original frame sequence invalid')
        last_native = native
        time_s = row.get('time_s')
        require(type(time_s) in (float, int) and math.isfinite(time_s) and
                abs(time_s - index / 20) < 1e-8, '20 Hz frame time invalid')
        now = stamp(row.get('civil_time'))
        require(now >= sunset - timedelta(days=1) and now <= sunrise + timedelta(days=1),
                'civil timestamp outside ephemeris interval')
        at_night = night_begin <= now <= night_end
        witness = row.get('visibility_1000ft')
        require(isinstance(witness, dict) and witness.get('native_frame') == native and
                witness.get('distance_m') == 304.8 and
                type(witness.get('person_discernible')) is bool and
                type(witness.get('vehicle_discernible')) is bool,
                'original 1000-foot person/vehicle discernibility missing')
        visibility_trigger = (not at_night and
                              (not witness['person_discernible'] or
                               not witness['vehicle_discernible']))
        parked = row.get('parked')
        require(type(parked) is bool, 'original parked state missing')
        require(type(row.get('headlamp_setting_on')) is bool and
                type(row.get('position_lamp_setting_on')) is bool,
                'original lamp setting missing')
        measured.append({'video_frame': index, 'native_frame': native,
                         'night_trigger': at_night,
                         'visibility_trigger': visibility_trigger,
                         'parked_exception_review_required': parked,
                         'headlamp_setting_on': row['headlamp_setting_on'],
                         'position_lamp_setting_on': row['position_lamp_setting_on']})
    return {'format': 'nrs-484d-100-1-activation-measure-v1',
            'source_kind': packet['source_kind'],
            'observation_sha256': hashlib.sha256(raw_observations).hexdigest(),
            'source_sha256': packet['source_sha256'],
            'night_begin': night_begin.isoformat(), 'night_end': night_end.isoformat(),
            'frames': measured,
            'class_equipment_sufficiency': None,
            'parked_exception_disposition': None,
            'actual_emitted_light_verified': False,
            'legal_result': None}


def measure_original(raw_trace, raw_frame_map, sources):
    """Join each original Native row to the sealed camera frame map before use."""
    require(isinstance(raw_trace, bytes) and isinstance(raw_frame_map, bytes),
            'original trace or frame map missing')
    try:
        trace = [json.loads(line) for line in raw_trace.splitlines() if line.strip()]
        mapping = [json.loads(line) for line in raw_frame_map.splitlines() if line.strip()]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('original trace or frame map invalid') from exc
    require(bool(trace) and len(trace) == len(mapping), 'original frame map length mismatch')
    for pose, row in zip(trace, mapping):
        require(all(pose.get(name) == row.get(name) for name in
                    ('video_frame', 'native_frame', 'camera_native_frames')) and
                pose.get('time_s') == row.get('time_s'),
                'original frame map join mismatch')
    packet = {'kind': 'lamp_observations', 'source_kind': 'native_saved_sample',
              'source_sha256': {name: hashlib.sha256(raw).hexdigest()
                                for name, raw in sources.items()}, 'frames': trace}
    result = measure(json.dumps(packet, sort_keys=True, separators=(',', ':')).encode(), sources)
    result['original_trace_sha256'] = hashlib.sha256(raw_trace).hexdigest()
    result['original_frame_map_sha256'] = hashlib.sha256(raw_frame_map).hexdigest()
    return result
