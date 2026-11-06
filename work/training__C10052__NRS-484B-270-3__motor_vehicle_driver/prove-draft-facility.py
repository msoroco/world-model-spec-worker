"""Build unselected 480-frame synthetic occupancy diagnostics and negatives."""
import json
from pathlib import Path

from native.geometry import (ALLEY_ENTRANCE_BOUNDS_M, BICYCLE_BOUNDS_M,
                             BICYCLE_LANE_ID, DRIVING_LANE_ID, ROAD_ID,
                             STOP_X_M, STOP_Y_M, body, check)
from native.measure_facility import EXCEPTIONS, measure

HERE = Path(__file__).resolve().parent
OUT = HERE / 'draft-facility'


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def build():
    check()
    OUT.mkdir(exist_ok=True)
    results = []
    for suffix, stop_y in STOP_Y_M.items():
        folder = OUT / suffix
        folder.mkdir(exist_ok=True)
        geometry = {'road_id': ROAD_ID, 'driving_lane_id': DRIVING_LANE_ID,
                    'bicycle_lane_id': BICYCLE_LANE_ID,
                    'bicycle_facility_native_xy_bounds_m': BICYCLE_BOUNDS_M,
                    'alley_entrance_native_xy_bounds_m': ALLEY_ENTRANCE_BOUNDS_M,
                    'native_facility_design_verified': False,
                    'scope': 'authored synthetic bounds; no Native facility designation readback'}
        (folder / 'road_geometry.json').write_text(json.dumps(geometry, indent=2) + '\n')
        context = {'source_kind': 'synthetic_scene_request',
                   'exceptions': {key: False for key in EXCEPTIONS},
                   'note': 'requested absence only; not observed or independently proven'}
        (folder / 'exception_context.json').write_text(json.dumps(context, indent=2) + '\n')
        rows = []
        for i in range(480):
            x = min(-45.0 + .25 * i, STOP_X_M)
            previous_x = min(-45.0 + .25 * (i-1), STOP_X_M) if i else x
            alpha = max(0.0, min(1.0, (x + 30.0) / 10.0))
            previous_alpha = max(0.0, min(1.0, (previous_x + 30.0) / 10.0))
            y = -1.5 + alpha * (stop_y + 1.5)
            previous_y = -1.5 + previous_alpha * (stop_y + 1.5)
            speed = 20 * ((x-previous_x)**2 + (y-previous_y)**2)**.5
            delta_x, delta_y = x-previous_x, y-previous_y
            travel = (delta_x**2 + delta_y**2)**.5
            forward = [delta_x/travel, delta_y/travel] if travel > 1e-9 else [1, 0]
            rows.append({'native_frame': 100+i, 'time_s': (i+1)/20,
                         'native_center_xy_m': [x, y], 'native_forward_xy': forward,
                         'native_body_xy_m': body(x, y, forward),
                         'native_road_id': ROAD_ID,
                         'native_lane_id': BICYCLE_LANE_ID if y < -3.0 else DRIVING_LANE_ID,
                         'speed_mps': speed, 'synthetic_diagnostic': True})
        samples = folder / 'native_samples.jsonl'
        write_rows(samples, rows)
        receipt = measure(samples, folder / 'road_geometry.json', folder / 'exception_context.json')
        expected = 0.0 if suffix == 'probe_a' else 1.8 * 5.2
        if abs(receipt['max_stopped_overlap_m2'] - expected) > 1e-6:
            raise ValueError('Unexpected synthetic stopped occupancy')
        if receipt['observed_exception_status'] != 'unresolved' or receipt['legal_verdict_claimed']:
            raise ValueError('Synthetic exception request was promoted to observed finding')
        (folder / 'measurement.json').write_text(json.dumps(receipt, indent=2) + '\n')
        negatives = {}
        for name, sample_path, geometry_path, context_path, expected_error in (
                ('missing-native-source', folder/'missing-native-samples.jsonl',
                 folder/'road_geometry.json', folder/'exception_context.json',
                 'Missing required source: missing-native-samples.jsonl'),
                ('missing-exception-source', samples, folder/'road_geometry.json',
                 folder/'missing-exception-context.json',
                 'Missing required source: missing-exception-context.json')):
            try:
                measure(sample_path, geometry_path, context_path)
            except ValueError as exc:
                if str(exc) != expected_error:
                    raise
                negatives[name] = str(exc)
            else:
                raise ValueError(name + ' accepted')
        wrong_road = folder / 'wrong-road.jsonl'
        write_rows(wrong_road, [{**r, 'native_road_id': 99} for r in rows])
        try:
            measure(wrong_road, folder/'road_geometry.json', folder/'exception_context.json')
        except ValueError as exc:
            if str(exc) != 'Wrong original road identity':
                raise
            negatives['wrong-road'] = str(exc)
        else:
            raise ValueError('Wrong road accepted')
        results.append({'case_suffix': suffix, 'frames': 480,
                        'max_stopped_overlap_m2': expected,
                        'source_sha256': receipt['source_sha256'],
                        'negatives': negatives, 'selected': False,
                        'scope': 'synthetic occupancy only; exceptions, Native facility and law unresolved'})
    summary = {'format': 'c10052-draft-facility-pair-v1', 'selected': False,
               'ready': False, 'rows': results}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
