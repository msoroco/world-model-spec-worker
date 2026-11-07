"""Save synthetic measurements crossing each C110919 red-turn fallback threshold."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE/'fallback-trigger-source.json'
OUTPUT = HERE/'fallback-trigger-summary.json'


def main():
    scenarios = {'baseline': (.20, 1.50, 60),
                 'route_error': (.60, 1.50, 60),
                 'clearance': (.20, .50, 60),
                 'pixel_margin': (.20, 1.50, 20)}
    rows = [{'case': case, 'scenario': label,
             'max_route_cross_track_error_m': route,
             'min_pedestrian_clearance_s': clearance,
             'min_signal_or_body_pixel_margin_px': pixels}
            for case in ('witness_1', 'witness_2')
            for label, (route, clearance, pixels) in scenarios.items()]
    SOURCE.write_text(json.dumps({'source_kind': 'synthetic_cpu_fixture',
                                  'measurements': rows}, indent=2)+'\n')
    decisions = [{'case': row['case'], 'scenario': row['scenario'],
                  'fallback1_trigger': row['max_route_cross_track_error_m'] > .45,
                  'fallback2_trigger': row['min_pedestrian_clearance_s'] < 1.0,
                  'fallback3_trigger': row['min_signal_or_body_pixel_margin_px'] < 40}
                 for row in rows]
    OUTPUT.write_text(json.dumps({'source_kind': 'synthetic_cpu_fixture',
        'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'original_native_observed': False, 'original_pixels_observed': False,
        'decisions': decisions}, indent=2)+'\n')
    print(json.dumps({'synthetic_measurements': len(rows),
                      'distinct_crossings_per_case': 3}))


if __name__ == '__main__':
    main()
