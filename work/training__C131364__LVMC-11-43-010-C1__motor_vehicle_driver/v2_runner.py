"""Check the current 600-frame roundabout request before any Native attempt."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root):
    config = json.loads((root / 'config.json').read_text())
    witness = config['case_id'].rsplit('__', 1)[-1]
    if witness not in ('witness_1', 'witness_2'):
        raise ValueError('Unknown roundabout witness')
    if config['duration_s'] != 30 or config['rate_hz'] != 20:
        raise ValueError('Full 600-frame duration required')
    if [c['name'] for c in config['cameras']] != [
            'overview', 'approach', 'reference_corner', 'driver_reference']:
        raise ValueError('Four source cameras required')
    track_path = root / 'authored-route.jsonl'
    road_path = root / 'road.xodr'
    if sha(track_path) != config['track_sha256'] or sha(road_path) != config['road_sha256']:
        raise ValueError('Exact roundabout source hash differs')
    if sha(root / 'assignment-source.json') != config['assignment_sha256']:
        raise ValueError('Frozen assignment source differs')
    if sha(root / 'case-plan.json') != config['case_plan_sha256']:
        raise ValueError('Current case plan source differs')
    road_ids = {int(road.attrib['id']) for road in ET.parse(road_path).getroot().findall('road')}
    if road_ids != {10, 11, 12}:
        raise ValueError('Entry, circulation and exit roads required')
    rows = [json.loads(line) for line in track_path.read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('600 route samples required')
    radius = 23.75 if witness == 'witness_1' else 27.25
    lane = -1 if witness == 'witness_1' else -2
    arc = radius * math.pi / 2
    phases = set()
    for frame, row in enumerate(rows):
        distance = min(6 * (frame + 1) / 20, 30 + arc + 20)
        if distance < 30:
            phase, road, x, y, heading = 'entry', 10, -30 + distance, -radius, 0
        elif distance < 30 + arc:
            theta = -math.pi / 2 + (distance - 30) / radius
            phase, road, x, y, heading = 'circulation', 11, radius * math.cos(theta), radius * math.sin(theta), math.degrees(theta + math.pi / 2)
        else:
            phase, road, x, y, heading = 'exit', 12, radius, distance - 30 - arc, 90
        if (row['frame'] != frame or row['witness'] != witness or
                row['lane_id'] != lane or row['phase'] != phase or row['road_id'] != road or
                abs(row['time_s'] - (frame + 1) / 20) > 1e-6 or
                abs(row['ego_x_m'] - x) > 1e-5 or abs(row['ego_y_m'] - y) > 1e-5 or
                abs(row['ego_heading_deg'] - heading) > 1e-5 or
                row['actual_exit_observed'] is not False or row['roundabout_verified'] is not False):
            raise ValueError('Roundabout route source differs at frame ' + str(frame))
        phases.add(phase)
    if phases != {'entry', 'circulation', 'exit'}:
        raise ValueError('Complete roundabout route phases required')
    return {'checked_frames': 600, 'witness': witness, 'source_kind': 'authored_request',
            'actual_exit_observed': False, 'roundabout_verified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not args.check:
        raise ValueError('Native execution has not been rebound to this current v2 package')
    print(json.dumps(check(Path.cwd())))
