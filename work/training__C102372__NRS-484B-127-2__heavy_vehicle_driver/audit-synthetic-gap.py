"""Independent raw-frame audit of the two unselected truck-gap CPU fixtures."""
import hashlib
import json
from pathlib import Path
import math
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / '.runtime-work/c102372-truck-gap'
CASES = {'probe_1': 165.0, 'probe_2': 140.0}
THRESHOLD_M = 152.4


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_case(case):
    path = FOLDER / case
    manifest = json.loads((path / 'source-manifest.json').read_text())
    if set(manifest['sha256']) != {'native_samples.jsonl', 'following_context.json', 'road.xodr'}:
        raise ValueError('Incomplete source inventory')
    for name, expected in manifest['sha256'].items():
        if sha(path / name) != expected:
            raise ValueError('Source hash differs: ' + name)
    rows = [json.loads(line) for line in (path / 'native_samples.jsonl').read_text().splitlines()]
    road = ET.parse(path / 'road.xodr').getroot().find('road')
    grades = [dict((key, float(value)) for key, value in node.attrib.items())
              for node in road.findall('elevationProfile/elevation')]
    if [row['s'] for row in grades] != [0, 100, 150, 200] or grades[2]['a'] != 4:
        raise ValueError('Hill-crest source differs')
    context = json.loads((path / 'following_context.json').read_text())
    if len(rows) != 480 or context['same_direction_lane_count'] != 1 or context['overtaking'] is not False:
        raise ValueError('Wrong 480-frame single-lane context')
    gaps = []
    road_gaps = []
    held = []
    for index, row in enumerate(rows):
        if row['native_frame'] != index or abs(row['time_s'] - index/20) > 1e-9:
            raise ValueError('Frame/time join differs')
        ego, lead = row['ego'], row['lead']
        for actor in (ego, lead):
            if actor['actor_class'] != 'truck_or_combination' or actor['road_id'] != 1 or actor['lane_id'] != -1:
                raise ValueError('Actor/road/lane context differs')
            if max(x[1] for x in actor['body_xy_m'])-min(x[1] for x in actor['body_xy_m']) < 2.032:
                raise ValueError('Below 80-inch class')
        gap = min(x[0] for x in lead['body_xy_m'])-max(x[0] for x in ego['body_xy_m'])
        gaps.append(gap)
        front = max(x[0] for x in ego['body_xy_m'])
        rear = min(x[0] for x in lead['body_xy_m'])
        count = math.ceil((rear-front)/.5)
        step = (rear-front)/count
        length = 0.0
        for item in range(count):
            station = front+(item+.5)*step
            grade = next(row for row in reversed(grades) if row['s'] <= station)
            offset = station-grade['s']
            slope = grade['b']+2*grade['c']*offset+3*grade['d']*offset*offset
            length += step*math.hypot(1, slope)
        road_gaps.append(length)
        held.append((row['native_frame'], row['time_s'], ego['body_xy_m'], ego['speed_mps'], lead['speed_mps']))
    return gaps, road_gaps, held, context, manifest


def main():
    one = read_case('probe_1');two = read_case('probe_2')
    if one[2] != two[2] or one[3] != two[3] or one[4]['sha256']['road.xodr'] != two[4]['sha256']['road.xodr']:
        raise ValueError('Controlled inputs differ beyond lead gap')
    for case, record in zip(CASES, (one, two)):
        if any(abs(gap-CASES[case]) > 1e-7 for gap in record[0]):
            raise ValueError('Measured body gap differs')
    if not min(one[1]) > THRESHOLD_M or not max(two[1]) < THRESHOLD_M:
        raise ValueError('500-foot sides differ')
    if not all(a <= b < a+.5 for record in (one, two) for a, b in zip(record[0], record[1])):
        raise ValueError('Road distance does not follow hill crest')
    print(json.dumps({'passed': True, 'frames_per_case': 480, 'gaps_m': CASES,
                      'threshold_m': THRESHOLD_M, 'held_inputs': True,
                      'physical_observation_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
