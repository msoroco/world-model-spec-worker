"""Measure original bus dwell; require sourced designation before comparing a limit."""
import argparse
import json
import math
from pathlib import Path


def measure(history_path, context_path):
    rows = [json.loads(line) for line in Path(history_path).read_text().splitlines()]
    context = json.loads(Path(context_path).read_text())
    if len(rows) != 600 or [r['video_frame'] for r in rows] != list(range(600)):
        raise ValueError('missing original 600-frame bus history')
    if not all(rows[i]['native_frame'] < rows[i + 1]['native_frame'] for i in range(599)):
        raise ValueError('nonmonotonic original Native frames')
    if not all(abs(r['time_s'] - i / 20) < .005 for i, r in enumerate(rows)):
        raise ValueError('original 20 Hz timing missing')
    survey = context.get('native_survey')
    if not survey or not survey.get('terminus_signal') or len(survey.get('parking_lane_samples', [])) != 4:
        raise ValueError('Native terminus and parking-zone survey missing')
    if context.get('zone_x_m') != [-2.0, 20.0] or context.get('parking_lane_id') != -2:
        raise ValueError('Native endpoint bounds missing')
    if len({r.get('subject_id') for r in rows}) != 1 or rows[0].get('subject_id') is None:
        raise ValueError('original bus identity missing')
    if len({r.get('blueprint_id') for r in rows}) != 1 or rows[0].get('blueprint_id') != 'vehicle.mitsubishi.fusorosa':
        raise ValueError('covered non-tour bus blueprint not established')
    parked = []
    for r in rows:
        pos, vel = r.get('position_xyz_m'), r.get('velocity_xyz_mps')
        if not isinstance(pos, list) or len(pos) != 3 or not all(type(v) in (int, float) and math.isfinite(v) for v in pos):
            raise ValueError('original bus position missing')
        if not isinstance(vel, list) or len(vel) != 3 or not all(type(v) in (int, float) and math.isfinite(v) for v in vel):
            raise ValueError('original bus velocity missing')
        speed = math.sqrt(sum(v * v for v in vel))
        parked.append(-2 <= pos[0] <= 20 and abs(pos[1] + 5.25) <= 1.5 and speed < .25)
    intervals = []
    start = None
    for i, flag in enumerate(parked + [False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            intervals.append({'first_frame': start, 'last_frame': i - 1, 'duration_s': (i - start) / 20})
            start = None
    if not intervals:
        raise ValueError('no original stationary bus occupancy at endpoint')
    complete = [v for v in intervals if v['first_frame'] > 0 and v['last_frame'] < 599]
    if not complete:
        raise ValueError('parking interval censored by capture boundary')
    longest = max(complete, key=lambda v: v['duration_s'])
    period = context.get('designated_period_s')
    verified = context.get('designation_verified') is True and bool(context.get('designation_authority_source'))
    if verified and (type(period) not in (int, float) or not math.isfinite(period) or period <= 0):
        raise ValueError('verified designation has no valid period')
    return {'frames': 600, 'parking_intervals': intervals, 'longest_complete_interval_s': longest['duration_s'], 'designated_period_s': period if verified else None, 'dwell_exceeds_verified_period': longest['duration_s'] > period if verified else None, 'designation_source': context['designation_authority_source'] if verified else None, 'legal_conclusion': None, 'physical_review_required': True, 'activity_classification_unverified': not context.get('actual_loading_activity_verified', False)}

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--history', required=True)
    p.add_argument('--context', required=True)
    a = p.parse_args()
    print(json.dumps(measure(a.history, a.context), sort_keys=True))
