"""Source-bound parked-departure trajectories for NRS 484B.410.

Distances, speed changes and onset are measured facts. No gap, TTC or braking
value is a legal definition of a movement made "with safety".
"""
from __future__ import annotations

import hashlib
import json
import math
from shapely.geometry import Polygon

ASSIGNMENT = 'training__C227853__NRS-484B-410__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def polygon(value, name):
    require(isinstance(value, list) and len(value) == 4, name + ' footprint missing')
    require(all(isinstance(p, list) and len(p) == 2 and
                all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                    for v in p) for p in value), name + ' footprint missing')
    result = Polygon(value)
    require(result.is_valid and result.area > 0, name + ' footprint invalid')
    return result


def measure(raw_trace, raw_context):
    packet, context = json.loads(raw_trace), json.loads(raw_context)
    require(packet.get('assignment_id') == ASSIGNMENT and context.get('assignment_id') == ASSIGNMENT,
            'assignment mismatch')
    kind = packet.get('source_kind')
    require(kind in ('synthetic_native_sample', 'native_saved_sample') and
            context.get('source_kind') == kind, 'source kind mismatch')
    for name in ('map_source_sha256', 'highway_boundary_source_sha256',
                 'highway_dedication_source_sha256', 'public_access_source_sha256',
                 'curb_permission_source_sha256', 'parking_purpose_source_sha256'):
        value = context.get(name)
        require(isinstance(value, str) and len(value) == 64 and
                all(c in '0123456789abcdef' for c in value), name + ' missing')
    require(context.get('state') == 'Nevada' and context.get('public_highway') is True,
            'Nevada highway source missing')
    require(type(context.get('parking_permitted')) is bool,
            'curb parking permission unresolved')
    require(context.get('initial_status') in ('parked_no_loading',
            'stopped_temporary', 'standing_passenger_exchange'),
            'initial stopped, standing or parked purpose unresolved')
    frames = packet.get('frames')
    require(isinstance(frames, list) and len(frames) >= 600,
            'recording shorter than 30 seconds')
    require(packet.get('ego_id') and packet.get('traffic_id') and
            packet['ego_id'] != packet['traffic_id'], 'participant identities missing')
    prior_native = None
    gaps, ego_speeds, traffic_speeds = [], [], []
    for i, row in enumerate(frames):
        t = row.get('time_s')
        require(row.get('video_frame') == i and isinstance(t, (int, float)) and
                math.isfinite(t) and abs(t-i/20) < 1e-8,
                'noncontiguous 20 Hz frames')
        native = row.get('native_frame')
        require(type(native) is int and (prior_native is None or native > prior_native),
                'Native frame order missing')
        prior_native = native
        cameras = row.get('camera_native_frames')
        require(isinstance(cameras, dict) and set(cameras) == set(CAMERAS) and
                all(cameras[n] == native for n in CAMERAS), 'four-camera frame join missing')
        require(row.get('ego_id') == packet['ego_id'] and
                row.get('traffic_id') == packet['traffic_id'], 'participant identity changed')
        require(row.get('ego_road_id') == context.get('road_id') and
                row.get('traffic_road_id') == context.get('road_id'),
                'participant left sourced highway')
        ego, traffic = polygon(row.get('ego_footprint_xy_m'), 'ego'), polygon(
            row.get('traffic_footprint_xy_m'), 'traffic')
        es, ts = row.get('ego_speed_mps'), row.get('traffic_speed_mps')
        require(all(isinstance(v, (int, float)) and not isinstance(v, bool) and
                    math.isfinite(v) and v >= 0 for v in (es, ts)),
                'participant velocity source missing')
        gaps.append(ego.distance(traffic))
        ego_speeds.append(float(es))
        traffic_speeds.append(float(ts))
    require(all(v <= .1 for v in ego_speeds[:100]),
            'initial stationary history missing')
    starts = [i for i in range(100, len(frames)) if ego_speeds[i] > .1]
    require(bool(starts), 'vehicle never starts')
    onset = starts[0]
    # Difference of original measured speed samples, never a hard-braking legal cutoff.
    braking = [max(0.0, (a-b)*20) for a,b in zip(traffic_speeds, traffic_speeds[1:])]
    return {'format':'nrs-484b-410-departure-diagnostic-v1',
            'assignment_id':ASSIGNMENT, 'source_kind':kind,
            'trace_sha256':digest(raw_trace), 'context_sha256':digest(raw_context),
            'frame_count':len(frames), 'duration_s':len(frames)/20,
            'ego_start_frame':onset, 'ego_start_time_s':onset/20,
            'surface_gap_at_start_m':gaps[onset],
            'minimum_surface_gap_during_first_10s_after_start_m':min(gaps[onset:min(len(gaps),onset+200)]),
            'max_observed_traffic_deceleration_mps2':max(braking),
            'traffic_speed_at_start_mps':traffic_speeds[onset],
            'parking_permitted_source_fact':context['parking_permitted'],
            'initial_status_source_fact':context['initial_status'],
            'legal_safety_result':None,
            'unresolved':['independent highway and curb-permission source review',
                          'whether movement could be made with safety',
                          'physical Native trajectories and actual pixels']}


def measure_original(raw_trace, raw_frame_map, raw_context, raw_opendrive):
    context = json.loads(raw_context)
    require(context.get('map_source_sha256') == digest(raw_opendrive),
            'OpenDRIVE source hash mismatch')
    traces = [json.loads(line) for line in raw_trace.splitlines() if line.strip()]
    frame_map = [json.loads(line) for line in raw_frame_map.splitlines() if line.strip()]
    require(len(traces) == len(frame_map) and bool(traces),
            'original frame map length mismatch')
    for trace, row in zip(traces, frame_map):
        require(all(trace.get(k) == row.get(k) for k in
                    ('video_frame','native_frame','camera_native_frames')) and
                abs(trace['time_s']-row['time_s']) < 1e-8,
                'original frame map join mismatch')
    packet = {'assignment_id':ASSIGNMENT, 'source_kind':context.get('source_kind'),
              'ego_id':traces[0]['ego_id'], 'traffic_id':traces[0]['traffic_id'],
              'frames':traces}
    result = measure(json.dumps(packet,sort_keys=True,separators=(',',':')).encode(),raw_context)
    result.update(original_trace_sha256=digest(raw_trace),
                  original_frame_map_sha256=digest(raw_frame_map),
                  original_opendrive_sha256=digest(raw_opendrive))
    return result
