"""Save synthetic measurements crossing each C110454 two-way intersection fallback threshold."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE/'statutory-fallback-trigger-source.json'
OUTPUT = HERE/'statutory-fallback-trigger-summary.json'


def main():
    scenarios = {'baseline': (.20, .10, 80),
                 'route_error': (.80, .10, 80),
                 'parking_speed': (.20, .80, 80),
                 'pixel_margin': (.20, .10, 20)}
    rows = [{'case': case, 'scenario': label,
             'max_route_cross_track_error_m': route,
             'parking_endpoint_speed_m_s': parking_speed,
             'min_ego_pixel_margin_px': pixels}
            for case in ('rail_reference', 'rail_contrast', 'oneway_absent', 'oneway_present')
            for label, (route, parking_speed, pixels) in scenarios.items()]
    SOURCE.write_text(json.dumps({'source_kind': 'synthetic_cpu_fixture',
                                  'measurements': rows}, indent=2)+'\n')
    decisions = [{'case': row['case'], 'scenario': row['scenario'],
                  'fallback1_trigger': row['max_route_cross_track_error_m'] > .45,
                  'fallback2_trigger': row['parking_endpoint_speed_m_s'] > .3,
                  'fallback3_trigger': row['min_ego_pixel_margin_px'] < 40}
                 for row in rows]
    OUTPUT.write_text(json.dumps({'source_kind': 'synthetic_cpu_fixture',
        'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'original_native_observed': False, 'original_pixels_observed': False,
        'decisions': decisions}, indent=2)+'\n')
    print(json.dumps({'synthetic_measurements': len(rows),
                      'distinct_crossings_per_case': 3}))


if __name__ == '__main__':
    main()
