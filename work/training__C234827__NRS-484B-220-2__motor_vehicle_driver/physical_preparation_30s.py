"""Assess joined rotary body passage without asserting a physical island or legal outcome."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(source, case_id, output):
    source = Path(source)
    rows = [json.loads(line) for line in source.read_text().splitlines()] if source.is_file() else []
    samples = []
    for row in rows:
        ego = row.get('ego', {})
        position = ego.get('center_native_xyz_m')
        if not isinstance(position, list) or len(position) < 2:
            continue
        x, y = float(position[0]), float(position[1])
        frame = row.get('native_frame', row.get('frame'))
        heading = ego.get('yaw_deg')
        body = ego.get('body_native_xyz_m')
        if not isinstance(heading, (int, float)) or not isinstance(body, list) or len(body) != 8:
            continue
        radial_clearance = min(math.hypot(float(point[0]), float(point[1])) - 15 for point in body)
        yaw = math.radians(heading)
        island_cross = math.cos(yaw) * -y - math.sin(yaw) * -x
        samples.append((frame, x, y, math.hypot(x, y), island_cross, radial_clearance))
    intervals = []
    for before, after in zip(samples, samples[1:]):
        angle = math.atan2(after[2], after[1]) - math.atan2(before[2], before[1])
        angle = (angle + math.pi) % (2 * math.pi) - math.pi
        intervals.append(angle)
    progress = sum(intervals)
    full = (len(samples) == 600 and len({item[0] for item in samples}) == 600
            and all(20.0 <= item[3] <= 28.5 and item[5] > 0 for item in samples)
            and abs(progress) >= 2 * math.pi and
            (all(value > 0 for value in intervals) or all(value < 0 for value in intervals)))
    status = 'unverified' if not source.is_file() or not samples else ('met' if full else 'not_met')
    sources = {source.name: sha(source)} if source.is_file() else {'missing': source.name}
    check = {'status': status, 'method': '600 source-shaped body centers and vertices, island-side bearing, rotary radii and uninterrupted wrapped angular increments; engineering completion only',
             'sources': sources, 'observed_frames': len(samples),
             'signed_progress_rad': round(progress, 6),
             'island_on_left_frames': sum(item[4] > 1 for item in samples),
             'island_on_right_frames': sum(item[4] < -1 for item in samples),
             'minimum_body_clearance_m': round(min((item[5] for item in samples), default=0), 4),
             'physical_island_verified': False}
    result = {'case_id': case_id, 'physical_checks': {'maneuver': check},
              'maneuver_completed': status == 'met',
              'realized_observables': {'signed_progress_rad': round(progress, 6)} if status == 'met' else {},
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': case_id, 'status': status, 'frames': len(samples),
                      'signed_progress_rad': round(progress, 6)}))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    assess(args.source, args.case, args.output)


if __name__ == '__main__':
    main()
