"""Source-bound C10052 candidate triggers; measurements are not legal findings."""
import hashlib
import json
import math
from pathlib import Path

VIEWS = ('overview', 'facility')
RATE_HZ = 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def evaluate(folder):
    folder = Path(folder)
    manifest = json.loads((folder / 'trigger-sources.json').read_text())
    if manifest.get('format') != 'c10052-trigger-sources-v1':
        raise ValueError('Unknown trigger source manifest')
    kind = manifest.get('source_kind')
    if kind not in ('synthetic_cpu_fixture', 'original_native'):
        raise ValueError('Unknown trigger source provenance')
    names = ('native_samples.jsonl', 'config.json', 'camera_visibility.jsonl')
    if set(manifest.get('sha256', {})) != set(names):
        raise ValueError('Incomplete trigger source hashes')
    for name in names:
        path = folder / name
        if not path.is_file() or sha(path) != manifest['sha256'][name]:
            raise ValueError('Trigger source hash differs: ' + name)
    config = json.loads((folder / 'config.json').read_text())
    samples = rows(folder / 'native_samples.jsonl')
    visibility = rows(folder / 'camera_visibility.jsonl')
    if len(samples) != 480 or len(visibility) != len(samples):
        raise ValueError('Trigger source frame counts differ')
    if kind == 'original_native' and any(row.get('synthetic_diagnostic') for row in samples):
        raise ValueError('Synthetic samples cannot be original Native')
    suffix = config.get('case_suffix')
    if suffix not in ('probe_a', 'probe_b'):
        raise ValueError('Unknown C10052 case suffix')
    target_y = -1.5 if suffix == 'probe_a' else -4.0
    target = (-12.0, target_y)
    previous_frame = -1
    previous_time = -math.inf
    stopped = []
    centers = []
    for sample, image in zip(samples, visibility):
        frame, time = sample.get('native_frame'), sample.get('time_s')
        xy = sample.get('native_center_xy_m')
        speed = sample.get('speed_mps')
        if (type(frame) is not int or frame <= previous_frame or
            not finite(time) or time <= previous_time or
            not isinstance(xy, list) or len(xy) != 2 or
            not all(finite(v) for v in xy) or
            not finite(speed) or speed < 0):
            raise ValueError('Invalid Native trigger sample')
        if previous_frame >= 0 and abs(time - previous_time - 1/RATE_HZ) > .002:
            raise ValueError('Trigger sample rate differs')
        if image.get('native_frame') != frame or image.get('time_s') != time:
            raise ValueError('Camera annotation frame join differs')
        if set(image.get('views', {})) != set(VIEWS) or any(
            set(image['views'][view]) != {'full_body', 'facility_edge'} or
            any(type(value) is not bool for value in image['views'][view].values())
            for view in VIEWS):
            raise ValueError('Invalid camera annotation')
        centers.append(xy)
        stopped.append(speed <= .1)
        previous_frame, previous_time = frame, time
    if kind == 'original_native' and any(row.get('synthetic_diagnostic') for row in visibility):
        raise ValueError('Synthetic camera annotation cannot be original Native')
    intervals = []
    start = None
    for index, flag in enumerate(stopped + [False]):
        if flag and start is None:
            start = index
        if not flag and start is not None:
            intervals.append((start, index))
            start = None
    stop_start, stop_end = max(intervals, key=lambda pair: pair[1]-pair[0])
    duration = (stop_end-stop_start)/RATE_HZ
    error = max(math.dist(centers[index], target) for index in range(stop_start, stop_end))
    initial_y = centers[0][1]
    shift = next((index for index, xy in enumerate(centers)
                  if abs(xy[1]-initial_y) >= .05), None)
    lead_in = None if shift is None else centers[shift][0]-centers[0][0]
    if lead_in is not None and lead_in < 0:
        raise ValueError('Lateral shift precedes route start')
    fractions = {view:sum(
        visibility[index]['views'][view]['full_body'] and
        visibility[index]['views'][view]['facility_edge']
        for index in range(stop_start, stop_end))/(stop_end-stop_start)
        for view in VIEWS}
    return {'format':'c10052-measured-fallback-triggers-v1',
            'case_suffix':suffix,'source_kind':kind,
            'source_sha256':manifest['sha256'],
            'frames':len(samples),'stop_interval_frames':[stop_start,stop_end],
            'route_lead_in_before_lateral_shift_m':lead_in,
            'maximum_stationary_target_error_m':error,
            'longest_stationary_duration_s':duration,
            'stopped_frame_visible_fraction':fractions,
            'fallback1_trigger_measured':bool(
                manifest.get('route_survey_passed') is False or
                (lead_in is not None and lead_in < 15)),
            'fallback2_trigger_measured':error > .25 or duration < 2,
            'fallback3_trigger_measured':min(fractions.values()) < .95,
            'physical_observation_claimed':kind == 'original_native',
            'legal_verdict_claimed':False}
