"""Complete synchronous Native capture loop for exact officer alternatives."""

import hashlib
import json
import math
from pathlib import Path

from officer_capture_step import step
from officer_direction import REFERENCE_SUFFIXES, behavior_suffix
from stopping_reference import ApproachState


FRAMES = 600
DELTA_S = 0.05


def run(carla, world, ego, other, officer, bone_adapter, case_id,
        reference, camera_readback, source_intake, *, before_tick=None,
        after_tick=None, hold_ticks=20, go_frame=300):
    suffix = behavior_suffix(case_id)
    settings = world.get_settings()
    delta = getattr(settings, 'fixed_delta_seconds', None)
    if (getattr(settings, 'synchronous_mode', None) is not True or
            type(delta) not in (int, float) or not math.isfinite(delta) or
            abs(delta - DELTA_S) > 1e-6):
        raise ValueError('Native synchronous 20 Hz world required')
    if not isinstance(reference, dict) or reference.get('kind') not in {
            'stop_line', 'near_crosswalk', 'nearest_view'} or not reference.get('source'):
        raise ValueError('Sourced stopping reference required')
    expected_kind = {'stop_line_reference': 'stop_line',
                     'crosswalk_reference': 'near_crosswalk',
                     'nearest_view_reference': 'nearest_view'}
    if suffix in REFERENCE_SUFFIXES and reference['kind'] != expected_kind[suffix]:
        raise ValueError('Exact stopping-reference case and authored site differ')
    site_sha = source_intake.get('site_sha256') if isinstance(source_intake, dict) else None
    if (not isinstance(site_sha, str) or len(site_sha) != 64 or
            any(c not in '0123456789abcdef' for c in site_sha)):
        raise ValueError('Authored officer site hash required')
    if before_tick is not None and not callable(before_tick):
        raise ValueError('Native pre-tick actor adapter required')
    if after_tick is not None and not callable(after_tick):
        raise ValueError('Native post-tick observer required')
    state = ApproachState()
    rows = []
    previous_frame = -1
    previous_time = None
    for index in range(FRAMES):
        if before_tick is not None:
            before_tick(index)
        row = step(carla, world, ego, other, officer, bone_adapter, case_id,
                   index, FRAMES, reference, state, camera_readback,
                   source_intake, hold_ticks=hold_ticks, go_frame=go_frame)
        snapshot = world.get_snapshot()
        if snapshot.frame != row['carla_frame']:
            raise ValueError('Native snapshot and capture frame differ')
        time_s = snapshot.timestamp.elapsed_seconds
        if type(time_s) not in (int, float) or not math.isfinite(time_s):
            raise ValueError('Native capture time missing')
        if row['carla_frame'] <= previous_frame:
            raise ValueError('Nonmonotone Native capture frame')
        if previous_time is not None and abs(time_s - previous_time - DELTA_S) > 1e-4:
            raise ValueError('Native capture rate differs from 20 Hz')
        row['time_s'] = float(time_s)
        rows.append(row)
        previous_frame, previous_time = row['carla_frame'], time_s
        if after_tick is not None:
            after_tick(row)
    return {'format': 'worker-subsection-2-officer-native-capture',
            'case_id': case_id, 'site_id': source_intake['site_id'],
            'site_sha256': site_sha,
            'fixed_delta_seconds': DELTA_S, 'frame_count': FRAMES,
            'first_carla_frame': rows[0]['carla_frame'],
            'last_carla_frame': rows[-1]['carla_frame'],
            'rows': rows, 'physical_visibility_judgment': 'unreviewed',
            'police_authority_judgment': 'unreviewed',
            'legal_exception_judgment': 'unresolved'}


def write_receipt(capture, destination):
    if (not isinstance(capture, dict) or
            capture.get('format') != 'worker-subsection-2-officer-native-capture' or
            capture.get('frame_count') != FRAMES or
            not isinstance(capture.get('rows'), list) or
            len(capture['rows']) != FRAMES):
        raise ValueError('Complete Native officer capture required')
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(capture, sort_keys=True, separators=(',', ':'),
                         allow_nan=False) + '\n'
    if len(payload.encode()) > 2 * 1024 * 1024:
        raise ValueError('Native officer receipt exceeds return-file limit')
    path.write_text(payload)
    return {'path': str(path), 'sha256': hashlib.sha256(payload.encode()).hexdigest()}
