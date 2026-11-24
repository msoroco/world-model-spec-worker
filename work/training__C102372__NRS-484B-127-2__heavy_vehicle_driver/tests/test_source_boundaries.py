"""Source-bound checks of the statute's distance and width boundaries."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parents[1]
SOURCE = HERE / 'selected-fixture' / 'probe_1'
MEASURE = HERE / 'native' / 'measure_gap.py'
spec = importlib.util.spec_from_file_location('truck_measure_gap', MEASURE)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def run() -> dict:
    original = json.loads((SOURCE / 'native_samples.jsonl').open().readline())
    road = ET.parse(SOURCE / 'road.xodr').getroot().find('road')
    assert road is not None
    profile = road.findall('elevationProfile/elevation')
    ego_front = max(x for x, _ in original['ego']['body_xy_m'])
    lead_rear = min(x for x, _ in original['lead']['body_xy_m'])
    original_road_gap = module.road_distance(ego_front, lead_rear, profile)
    assert original_road_gap > module.GAP_LIMIT_M

    # Find the original-road station at the exact legal boundary. The bisection
    # resolution is a numerical measurement tolerance, not a legal exception.
    lo, hi = ego_front, lead_rear
    for _ in range(42):
        mid = (lo + hi) / 2
        if module.road_distance(ego_front, mid, profile) < module.GAP_LIMIT_M:
            lo = mid
        else:
            hi = mid
    at_station = (lo + hi) / 2
    samples = []
    for label, target_ft in (('below', 499.0), ('at', 500.0), ('above', 501.0)):
        target_m = target_ft * 0.3048
        low, high = ego_front, lead_rear
        for _ in range(42):
            mid = (low + high) / 2
            if module.road_distance(ego_front, mid, profile) < target_m:
                low = mid
            else:
                high = mid
        station = (low + high) / 2
        observed = module.road_distance(ego_front, station, profile)
        assert abs(observed - target_m) < 1e-8
        legal_relation = ('below' if target_ft < 500 else
                          'at' if target_ft == 500 else 'above')
        assert legal_relation == label
        samples.append({'relation': label, 'target_ft': target_ft,
                        'target_m': target_m, 'lead_rear_station_m': station,
                        'measured_road_arc_m': observed})

    widths = []
    for actor_name in ('ego', 'lead'):
        original_width = max(y for _, y in original[actor_name]['body_xy_m']) - min(
            y for _, y in original[actor_name]['body_xy_m'])
        assert original_width > module.WIDTH_MIN_M
        for label, width_in in (('below', 79.99), ('at', 80.0)):
            width_m = width_in * 0.0254
            assert (width_m >= module.WIDTH_MIN_M) == (label == 'at')
            widths.append({'actor': actor_name, 'relation': label,
                           'width_in': width_in, 'width_m': width_m,
                           'qualifies_by_exact_source_threshold': label == 'at'})
    return {
        'format': 'c102372-source-boundary-proof-v1',
        'source_sha256': {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest()
                          for name in ('native_samples.jsonl', 'road.xodr')},
        'source_frame': original['native_frame'],
        'statutory_boundaries': {'gap_ft': 500, 'gap_m': module.GAP_LIMIT_M,
                                 'overall_width_in': 80, 'overall_width_m': module.WIDTH_MIN_M},
        'engineering_resolution': {
            'road_station_bisection_m': abs(hi - lo),
            'road_arc_assertion_m': 1e-8,
            'existing_measurer_uncertainty_band_m': 0.1,
            'legal_threshold_changed_by_uncertainty': False},
        'original_source_road_arc_gap_m': original_road_gap,
        'distance_boundary_samples': samples,
        'width_boundary_samples': widths,
        'legal_verdict_claimed': False}


if __name__ == '__main__':
    proof = run()
    output = HERE / 'source-boundary-proof.json'
    output.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'distance_sides': [v['relation'] for v in proof['distance_boundary_samples']],
                      'width_sides': [v['relation'] for v in proof['width_boundary_samples']],
                      'source_frame': proof['source_frame']}, sort_keys=True))
