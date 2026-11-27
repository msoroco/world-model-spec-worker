"""Measure original consecutive caravan spaces without legal classification."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from engineering import FRAMES, RATE_HZ
from geometry import CARAVAN_LANE_ID, ENTRANT_LANE_ID, ROAD_ID

REQUIRED = {'lead', 'ego_combination', 'trailer_proxy', 'rear', 'potential_entrant'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bounds(actor):
    points = actor.get('native_body_xy_m')
    if not isinstance(points, list) or len(points) != 4 or any(not isinstance(p, list) or len(p) != 2 for p in points):
        raise ValueError('Original four-corner actor body missing')
    xs = [float(p[0]) for p in points]
    if any(not math.isfinite(x) for x in xs) or min(xs) >= max(xs):
        raise ValueError('Original actor body extent invalid')
    return min(xs), max(xs)


def measure(folder):
    folder = Path(folder)
    source = json.loads((folder / 'source-manifest.json').read_text())
    if source.get('format') != 'c228508-original-native-draft-sources-v1':
        raise ValueError('Original Native source manifest differs')
    expected = {'authored-context.json', 'native_samples.jsonl'}
    if set(source.get('sha256', {})) != expected:
        raise ValueError('Original Native source inventory incomplete')
    for name in expected:
        if digest(folder / name) != source['sha256'][name]:
            raise ValueError('Original Native source hash differs: ' + name)
    context = json.loads((folder / 'authored-context.json').read_text())
    if context.get('case_id') != source.get('case_id') or context.get('candidate_id') != source.get('candidate_id'):
        raise ValueError('Original context identity differs')
    rows = [json.loads(line) for line in (folder / 'native_samples.jsonl').read_text().splitlines()]
    if len(rows) != FRAMES:
        raise ValueError('Original 600-frame Native window incomplete')
    spaces = {'lead_to_combination_m': [], 'combination_to_rear_m': []}
    entrant_lengths = []
    entrant_lanes = []
    observed_forward_frames = 0
    prior_frame = None
    prior_time = None
    for row in rows:
        frame, time_s = row.get('native_frame'), row.get('time_s')
        if type(frame) is not int or not isinstance(time_s, (int, float)) or not math.isfinite(time_s):
            raise ValueError('Original Native frame/time missing')
        if prior_frame is not None and (frame != prior_frame + 1 or abs(time_s - prior_time - 1 / RATE_HZ) > .005):
            raise ValueError('Original Native frame/time join differs')
        prior_frame, prior_time = frame, time_s
        actors = row.get('actors', {})
        if set(actors) != REQUIRED:
            raise ValueError('Original complete caravan actor inventory missing')
        for name, actor in actors.items():
            permitted_lanes = (ENTRANT_LANE_ID, CARAVAN_LANE_ID) if name == 'potential_entrant' else (CARAVAN_LANE_ID,)
            if actor.get('native_road_id') != ROAD_ID or actor.get('native_lane_id') not in permitted_lanes:
                raise ValueError('Original caravan lane/road identity differs')
            if not isinstance(actor.get('speed_mps'), (int, float)) or not math.isfinite(actor['speed_mps']):
                raise ValueError('Original actor velocity missing')
            velocity = actor.get('native_velocity_xy_mps')
            if not isinstance(velocity, list) or len(velocity) != 2 or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in velocity):
                raise ValueError('Original velocity vector missing')
            if name != 'potential_entrant' and velocity[0] < -0.1:
                raise ValueError('Original caravan actor reversed direction')
        if all(actors[name]['native_velocity_xy_mps'][0] > .1 for name in ('lead', 'ego_combination', 'trailer_proxy', 'rear')):
            observed_forward_frames += 1
        lead = bounds(actors['lead'])
        tractor = bounds(actors['ego_combination'])
        trailer = bounds(actors['trailer_proxy'])
        rear = bounds(actors['rear'])
        entrant = bounds(actors['potential_entrant'])
        entrant_lanes.append(actors['potential_entrant']['native_lane_id'])
        combination = (min(tractor[0], trailer[0]), max(tractor[1], trailer[1]))
        front_gap = lead[0] - combination[1]
        rear_gap = combination[0] - rear[1]
        if min(front_gap, rear_gap) < 0:
            raise ValueError('Original consecutive caravan bodies overlap or reverse')
        spaces['lead_to_combination_m'].append(front_gap)
        spaces['combination_to_rear_m'].append(rear_gap)
        entrant_lengths.append(entrant[1] - entrant[0])
    result = {'format': 'c228508-original-caravan-space-measurement-v1',
              'case_id': source['case_id'], 'candidate_id': source['candidate_id'],
              'source_sha256': source['sha256'], 'frame_count': FRAMES,
              'rate_hz': RATE_HZ,
              'minimum_clear_space_m': {name: round(min(values), 6) for name, values in spaces.items()},
              'maximum_potential_entrant_length_m': round(max(entrant_lengths), 6),
              'entrant_lane_ids_observed': sorted(set(entrant_lanes)),
              'entrant_transition_observed': entrant_lanes[0] == ENTRANT_LANE_ID and entrant_lanes[-1] == CARAVAN_LANE_ID,
              'all_caravan_actors_forward_frames': observed_forward_frames,
              'minimum_static_length_surplus_m': {name: round(min(values) - max(entrant_lengths), 6) for name, values in spaces.items()},
              'public_highway_status_verified': False,
              'outside_business_district_verified': False,
              'caravan_membership_verified': False,
              'trailer_coupling_verified': False,
              'entry_without_danger_judgment': 'unresolved',
              'physical_success_claimed': False, 'legal_verdict_claimed': False}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    destination = Path(args.output)
    if destination.exists():
        raise ValueError('Retain previous measurement; choose a new output')
    destination.write_text(json.dumps(measure(args.attempt), indent=2) + '\n')


if __name__ == '__main__':
    main()
