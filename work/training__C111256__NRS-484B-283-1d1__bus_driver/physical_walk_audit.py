"""Source joined Walk and bus response classifier; production requires original review."""
from __future__ import annotations

import json
import sys
from pathlib import Path

NATIVE_DIR = Path(__file__).resolve().parent / 'native'
if not NATIVE_DIR.is_dir():
    NATIVE_DIR = Path(__file__).resolve().parent
if str(NATIVE_DIR) not in sys.path:
    sys.path.insert(0, str(NATIVE_DIR))
from measure_walk import read_rows

LIFECYCLE = ('capture_finished', 'encoders_closed', 'restoration_verified',
             'native_exit', 'owner_released', 'saved_processing_started')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rectangle(body):
    require(isinstance(body, list) and len(body) == 4 and all(
        isinstance(p, list) and len(p) == 2 and all(type(value) in (int, float)
            for value in p) for p in body), 'Missing full participant body')
    return (min(p[0] for p in body), max(p[0] for p in body),
            min(p[1] for p in body), max(p[1] for p in body))


def intersects(a, b):
    return a[0] <= b[1] and a[1] >= b[0] and a[2] <= b[3] and a[3] >= b[2]


def classify(samples, mapping, geometry, suffix):
    require(suffix in ('reference', 'contrast') or
            suffix.startswith('right_of_way_physical_context-'),
            'Unknown Walk response case')
    require(len(samples) == len(mapping) == 480 and
            geometry.get('crosswalk_y_range_m') == [-12.0, -10.0] and
            geometry.get('bus_lane_x_range_m') == [0.0, 3.5],
            'Missing complete original Walk source geometry or frame history')
    strip = (0.0, 3.5, -12.0, -10.0)
    pedestrian_positions = []
    directed = []
    overlapping = []
    prior_frame = -1
    prior_time = -1.0
    for index, (sample, frame) in enumerate(zip(samples, mapping)):
        native_frame = sample.get('native_frame')
        time_s = sample.get('time_s')
        require(type(native_frame) is int and native_frame > prior_frame and
                type(time_s) in (int, float) and time_s > prior_time and
                frame.get('video_frame') == index and
                frame.get('native_frame') == native_frame and
                abs(frame.get('time_s', -1) - time_s) < 1e-4,
                'Walk physical frame/time join differs')
        prior_frame, prior_time = native_frame, time_s
        require(sample.get('walk_signal_actor_id') == geometry.get('walk_signal_id') and
                type(sample.get('pedestrian_actor_id')) is int and
                type(sample.get('bus_actor_id')) is int and
                sample['pedestrian_actor_id'] != sample['bus_actor_id'] and
                sample.get('walk_signal_display_observed') in
                ('Walk', 'DontWalk', 'Wait', 'Unknown') and
                type(sample.get('pedestrian_facing_signal')) is bool,
                'Walk physical signal or participant identity differs')
        bus = rectangle(sample.get('bus_body_xy_m'))
        pedestrian = rectangle(sample.get('pedestrian_body_xy_m'))
        pedestrian_positions.append(pedestrian)
        if (sample['walk_signal_display_observed'] == 'Walk' and
                sample['pedestrian_facing_signal'] and intersects(pedestrian, strip)):
            directed.append(index)
            if intersects(bus, strip):
                overlapping.append(index)
    traversed = pedestrian_positions[0][1] < strip[0] and \
        pedestrian_positions[-1][0] > strip[1]
    bus_response = bool(overlapping) if suffix == 'contrast' else not overlapping
    status = 'met' if traversed and directed and bus_response else 'not_met'
    return {'status': status, 'frames': 480,
            'pedestrian_crossing_completed': traversed,
            'directed_walk_crosswalk_frames': len(directed),
            'simultaneous_bus_pedestrian_frames': len(overlapping),
            'requested_bus_response_observed': bus_response,
            'first_directed_frame': directed[0] if directed else None,
            'first_simultaneous_frame': overlapping[0] if overlapping else None}


def check_lifecycle(events):
    require(tuple(events) == LIFECYCLE,
            'Saved processing must follow encoders, restoration, Native exit and owner release')
    return {'events': list(events), 'saved_processing_after_owner_release': True}


def audit_original(attempt, suffix, review_path):
    """Use only original Native sources and independent official Walk pixel review."""
    from finalize import joined_sources, source
    from official_walk_source_audit import audit_original as audit_walk

    attempt = Path(attempt)
    capture = json.loads(source(attempt, 'capture/manifest.json').read_text())
    require(capture.get('synthetic_diagnostic') is False,
            'Synthetic source cannot prove original Native Walk motion')
    official = audit_walk(attempt, review_path)
    samples, mapping, geometry, synthetic, joins = joined_sources(attempt, 480)
    require(synthetic is False, 'Synthetic source cannot prove original Native Walk motion')
    review = json.loads(Path(review_path).read_text())
    effective = []
    for sample, observed in zip(samples, review['observations']):
        effective.append({**sample,
            'walk_signal_display_observed': observed['display'],
            'pedestrian_facing_signal': observed['pedestrian_facing_signal']})
    measured = classify(effective, mapping, geometry, suffix)
    return {'format': 'c111256-original-physical-walk-audit-v1',
            'case_suffix': suffix, 'physical_checks': {'maneuver': measured},
            'official_walk_audit': official, 'source_joins': joins,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


def diagnostic_source(attempt, suffix):
    attempt = Path(attempt)
    geometry = json.loads((attempt / 'road_geometry.json').read_text())
    require(geometry.get('synthetic_diagnostic') is True,
            'Diagnostic source must retain synthetic provenance')
    return classify(read_rows(attempt / 'native_samples.jsonl'),
                    read_rows(attempt / 'video_frames.jsonl'), geometry, suffix)
