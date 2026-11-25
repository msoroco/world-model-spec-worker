"""Audit synthetic diagnostic poses against the authored OpenDRIVE lane geometry."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROUTES = {'through': (4, 13, 1), 'entrant': (3, 14, 2)}
LANES = {'through': 1, 'entrant': -1}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def road_geometry(path):
    result = {}
    for road in ET.parse(path).findall('road'):
        number = int(road.attrib['id'])
        element = road.find('planView/geometry')
        if element is None or element.find('line') is None:
            raise ValueError('Expected straight authored road absent')
        lanes = {}
        for lane in road.findall('lanes/laneSection/left/lane') + road.findall('lanes/laneSection/right/lane'):
            if lane.attrib.get('type') != 'driving':
                continue
            width = lane.find('width')
            if width is None or any(float(width.attrib.get(k, 0)) for k in ('b', 'c', 'd')):
                raise ValueError('Variable lane width cannot be audited')
            lanes[int(lane.attrib['id'])] = float(width.attrib['a'])
        result[number] = (float(element.attrib['x']), float(element.attrib['y']),
                          float(element.attrib['hdg']), float(element.attrib['length']), lanes)
    return result


def audit(case, source, road):
    geometry = road_geometry(road)
    if set(geometry) != {1, 2, 3, 4, 13, 14}:
        raise ValueError('Authored road inventory differs')
    rows = [json.loads(line) for line in Path(source).read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Full source window absent')
    max_error = {'through': 0.0, 'entrant': 0.0}
    route_seen = {'through': set(), 'entrant': set()}
    for index, row in enumerate(rows):
        if row.get('video_frame') != index or row.get('native_frame') != 100 + index:
            raise ValueError('Source frame join differs')
        for role in ROUTES:
            actor = row[role]
            road_id, lane_id = actor['road_id'], actor['lane_id']
            if road_id not in ROUTES[role] or lane_id != LANES[role]:
                raise ValueError(f'{role} road/lane role differs at frame {index}')
            x0, y0, heading, length, widths = geometry[road_id]
            if lane_id not in widths or not math.isclose(widths[lane_id], 3.5, abs_tol=1e-6):
                raise ValueError(f'{role} authored lane width differs')
            dx, dy = actor['x_m'] - x0, actor['y_m'] - y0
            along = dx * math.cos(heading) + dy * math.sin(heading)
            across = -dx * math.sin(heading) + dy * math.cos(heading)
            expected_center = widths[lane_id] / 2 if lane_id > 0 else -widths[lane_id] / 2
            error = abs(across - expected_center)
            if along < -1e-6 or along > length + 1e-6 or error > .25:
                raise ValueError(f'{role} pose outside authored lane at frame {index}')
            max_error[role] = max(max_error[role], error)
            route_seen[role].add(road_id)
    if any(route_seen[role] != set(ROUTES[role]) for role in ROUTES):
        raise ValueError('Full actor route absent')
    return {'case_id': case, 'frames': len(rows), 'road_sha256': sha(road),
            'source_sha256': sha(source), 'route_seen': {k: sorted(v) for k, v in route_seen.items()},
            'max_lane_center_error_m': max_error, 'physical_observation_claimed': False}


def reject(label, case, rows, road, expected):
    scratch = HERE.parents[1] / '.runtime-work' / 'c111294-geometry-output' / 'geometry-negatives'
    scratch.mkdir(parents=True, exist_ok=True)
    source = scratch / (label + '.jsonl')
    source.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    try:
        audit(case, source, road)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f'{label}: unexpected rejection {error}') from error
        return {'label': label, 'source_sha256': sha(source), 'rejection': str(error)}
    raise AssertionError(f'{label}: invalid pose accepted')


def main():
    positives = []
    for number in (1, 2):
        case = HERE.name + f'__probe_{number}'
        fixture = HERE / f'current-v2-probe-{number}-fixture'
        positives.append(audit(case, fixture / 'native_samples.jsonl', fixture / 'road.xodr'))
    case = positives[0]['case_id']
    fixture = HERE / 'current-v2-probe-1-fixture'
    rows = [json.loads(line) for line in (fixture / 'native_samples.jsonl').read_text().splitlines()]
    import copy
    negatives = []
    changed = copy.deepcopy(rows)
    changed[0]['through']['x_m'] = 0.0
    negatives.append(reject('centerline', case, changed, fixture / 'road.xodr', 'pose outside authored lane'))
    changed = copy.deepcopy(rows)
    changed[0]['through']['road_id'] = 1
    negatives.append(reject('reversed-road', case, changed, fixture / 'road.xodr', 'pose outside authored lane'))
    changed = copy.deepcopy(rows)
    changed[0]['entrant']['lane_id'] = 1
    negatives.append(reject('wrong-entrant-lane', case, changed, fixture / 'road.xodr', 'road/lane role differs'))
    receipt = {'format': 'c111294-authored-lane-audit-v1', 'passed': True,
               'positive': positives, 'negative': negatives,
               'auditor_sha256': sha(Path(__file__)), 'physical_observation_claimed': False}
    output = HERE / 'authored-road-geometry-audit.json'
    output.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': True, 'positive_count': 2, 'negative_count': len(negatives),
                      'receipt_sha256': sha(output)}))


if __name__ == '__main__':
    main()
