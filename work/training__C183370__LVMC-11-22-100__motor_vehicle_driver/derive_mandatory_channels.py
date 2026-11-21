"""Derive measured C183370 speed and surveyed contact from retained raw rows.

The output is a CPU preparation artifact. Polygon contact alone cannot prove
that pavement was newly laid or that a person actually warned the driver.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def derive(source, output):
    source, output = Path(source), Path(output)
    actor_file = source / 'native-actors.jsonl'
    frame_file = source / 'video_frames.jsonl'
    readback_file = source / 'live-readback.json'
    actors, frames = _rows(actor_file), _rows(frame_file)
    readback = json.loads(readback_file.read_text())
    plan = readback['plan']
    polygon_key = 'laid_polygon_xy_m' if 'laid_polygon_xy_m' in plan else 'repair_polygon_xy_m'
    polygon = Polygon(plan[polygon_key])
    if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
        raise ValueError('Invalid surveyed pavement polygon')
    if len(actors) != len(frames) or len(actors) < 600:
        raise ValueError('Actor/frame source length or 30-second coverage differs')
    if output.exists():
        raise ValueError('Preserve prior derived output; select a fresh directory')
    source_hashes = {name: _sha(source / name) for name in
                     ('native-actors.jsonl', 'video_frames.jsonl', 'live-readback.json')}
    speed_rows, contact_rows, condition_rows = [], [], []
    for index, (actor, frame) in enumerate(zip(actors, frames)):
        frame_id = frame['carla_frame']
        time_s = frame['time_s']
        if actor.get('carla_frame', actor.get('frame')) != frame_id:
            raise ValueError('Actor/frame identity differs')
        if index and (frame_id <= frames[index - 1]['carla_frame'] or
                      time_s <= frames[index - 1]['time_s']):
            raise ValueError('Source frames are not ordered')
        velocity = actor['ego_velocity_xyz_mps']
        speed = math.sqrt(sum(float(value) ** 2 for value in velocity))
        if not math.isfinite(speed) or abs(speed - actor['ego_speed_mps']) > 1e-5:
            raise ValueError('Native speed differs from source velocity')
        vertices = actor['ego_body_vertices_xyz_m']
        if len(vertices) < 4:
            raise ValueError('Ego body polygon is incomplete')
        body = MultiPoint([(float(v[0]), float(v[1])) for v in vertices]).convex_hull
        contact = bool(body.intersects(polygon))
        common = {'frame': frame_id, 'time_s': time_s,
                  'source_hashes': source_hashes}
        speed_rows.append({**common, 'value': speed, 'unit': 'm/s'})
        contact_rows.append({**common, 'value': contact,
                             'surveyed_region_kind': 'laid' if polygon_key.startswith('laid') else 'repair',
                             'surface_age_verified': False, 'warning_act_verified': False})
        condition_rows.append({**common, 'value': {
            'surveyed_polygon_contact': contact,
            'surveyed_region_kind': 'laid' if polygon_key.startswith('laid') else 'repair',
            'warning_person_actor_id': actor.get('warning_person_actor_id'),
            'warning_act_verified': False,
            'newly_laid_or_repaired_status_verified': False,
            'drive_over_warned_new_pavement': None,
            'reason': 'Original warning act and pavement condition require source review',
        }})
    if frames[-1]['time_s'] - frames[0]['time_s'] < 29.9:
        raise ValueError('Source time window is shorter than 30 seconds')
    output.mkdir(parents=True)
    for name, rows in (('ego_speed', speed_rows),
                       ('newly_laid_footprint_contact', contact_rows),
                       ('drive_over_warned_new_pavement', condition_rows)):
        (output / (name + '.jsonl')).write_text(''.join(json.dumps(row, allow_nan=False,
            sort_keys=True) + '\n' for row in rows))
    receipt = {'format': 'c183370-source-derived-channels-v1',
               'source_hashes': source_hashes, 'frames': len(frames),
               'duration_s': frames[-1]['time_s'] - frames[0]['time_s'],
               'channels': {name: _sha(output / (name + '.jsonl')) for name in
                            ('ego_speed', 'newly_laid_footprint_contact',
                             'drive_over_warned_new_pavement')},
               'original_native_verified': False, 'physical_acceptance_claimed': False,
               'warning_and_surface_status_verified': False}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(derive(args.source, args.output), sort_keys=True))


if __name__ == '__main__':
    main()
