"""Saved original velocity measurement across roundabout exit; no physical verdict."""
import argparse
import json
import math
from decimal import Decimal
from pathlib import Path

MPH_PER_MPS = 1 / 0.44704
LIMIT_MPH = 80.0
LIMIT_MPS_SQUARED = Decimal('35.7632') ** 2

def measure(history_path, survey_path):
    rows = [json.loads(line) for line in Path(history_path).read_text().splitlines()]
    seen = json.loads(Path(survey_path).read_text())
    if len(rows) != 600 or [r['video_frame'] for r in rows] != list(range(600)):
        raise ValueError('missing original 600-frame roundabout speed history')
    if not all(rows[i]['native_frame'] < rows[i + 1]['native_frame'] for i in range(599)):
        raise ValueError('nonmonotonic original Native frames')
    if not all(abs(r['time_s'] - i / 20) < .005 for i, r in enumerate(rows)):
        raise ValueError('original 20 Hz timing missing')
    if len(seen) != 8 or {(r['road_id'], r['lane_id']) for r in seen} != {(1,-1),(1,-2),(2,-1),(2,-2)}:
        raise ValueError('Native two-lane arc/exit survey missing')
    if len({r.get('subject_id') for r in rows}) != 1 or rows[0].get('subject_id') is None:
        raise ValueError('original vehicle identity missing')
    roads = [r.get('road_id') for r in rows]
    lanes = [r.get('lane_id') for r in rows]
    if roads[0] != 1 or 2 not in roads or roads[-1] != 2 or any(v not in (-1,-2) for v in lanes):
        raise ValueError('original roundabout exit traversal missing')
    speeds = []
    above = []
    for r in rows:
        vec = r.get('velocity_xyz_mps')
        if not isinstance(vec, list) or len(vec) != 3 or not all(type(x) in (int,float) and math.isfinite(x) for x in vec):
            raise ValueError('original velocity vector missing')
        magnitude = math.sqrt(sum(x*x for x in vec))
        speeds.append(magnitude * MPH_PER_MPS)
        above.append(sum(Decimal(str(x)) ** 2 for x in vec) > LIMIT_MPS_SQUARED)
    exit_frame = next(i for i, road in enumerate(roads) if road == 2)
    return {'frames': 600, 'first_exit_road_frame': exit_frame, 'maximum_full_trace_mph': max(speeds), 'maximum_on_arc_mph': max(s for s, road in zip(speeds, roads) if road == 1), 'maximum_on_exit_mph': max(s for s, road in zip(speeds, roads) if road == 2), 'samples_above_80_mph': sum(above), 'speed_samples_mph': speeds, 'boundary_comparison': 'Decimal original velocity magnitude squared > (35.7632 m/s)^2', 'legal_conclusion': None, 'physical_review_required': True}

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--history', required=True)
    p.add_argument('--survey', required=True)
    a = p.parse_args()
    print(json.dumps(measure(a.history, a.survey), sort_keys=True))
