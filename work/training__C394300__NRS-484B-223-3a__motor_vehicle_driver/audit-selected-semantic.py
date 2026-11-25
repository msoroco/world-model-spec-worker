"""Independent source audit for the center turn lane omitted by Core projection."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from shapely.geometry import Point, Polygon

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('lane_source', HERE / 'prove-center-lane-semantic.py')
SOURCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SOURCE)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(source):
    source = Path(source)
    xodr = source / 'scene.xodr'
    regions = SOURCE.source_regions(xodr.read_text())
    by_road = {r['road_id']: Polygon(r['boundary']) for r in regions}
    survey = json.loads((source / 'road_geometry.json').read_text())
    if survey['authored_map_sha256'] != sha(xodr):
        raise ValueError('Native survey changed authored center-turn map')
    samples = rows(source / 'native_samples.jsonl')
    mapping = rows(source / 'video_frames.jsonl')
    if len(samples) != 480 or len(mapping) != 480:
        raise ValueError('Incomplete original center-lane source interval')
    occupied = []
    for index, (sample, frame) in enumerate(zip(samples, mapping)):
        if sample['native_frame'] != frame['native_frame'] or frame['video_frame'] != index:
            raise ValueError('Original center-lane frame join differs')
        if abs(sample['time_s'] - frame['time_s']) > 1e-4:
            raise ValueError('Original center-lane time join differs')
        road = sample['native_road_id']
        if road not in by_road or sample['native_lane_id'] != -1:
            continue
        body = sample['native_body_xy_m']
        if len(body) != 4 or not all(by_road[road].covers(Point(*xy)) for xy in body):
            continue
        occupied.append(index)
    if not occupied:
        raise ValueError('No source-bound full-body center-turn occupancy')
    return {'format': 'c394300-selected-center-lane-source-audit',
            'passed': True, 'frames': len(samples),
            'authored_center_roads': sorted(by_road),
            'source_full_body_center_frames': len(occupied),
            'first_center_frame': occupied[0], 'last_center_frame': occupied[-1],
            'map_sha256': sha(xodr), 'survey_sha256': sha(source / 'road_geometry.json'),
            'samples_sha256': sha(source / 'native_samples.jsonl'),
            'source_kind': survey['source_kind'],
            'native_lane_types_observed_in_carla': survey['native_lane_types_observed_in_carla'],
            'core_center_lane_projection_claimed': False,
            'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('controlled_1', 'controlled_2'), required=True)
    args = parser.parse_args()
    source = HERE / 'selected-v2-source' / args.case
    print(json.dumps(audit(source), sort_keys=True))


if __name__ == '__main__':
    main()
