"""Exercise exact curb boundary arithmetic on explicitly synthetic rows."""
import json
from pathlib import Path

from bus_curb import CASES, measure_original

HERE = Path(__file__).resolve().parent


def build():
    summaries = []
    for case in CASES:
        construction = json.loads((HERE / ('construction-diagnostic-' + case.name + '.json')).read_text())
        files = {item['path']: item['content'] for item in construction['files']}
        scene = json.loads(files['scene.json'])
        rows = []
        for frame in range(900):
            row = {'original_frame': frame, 'time_s': frame / 20,
                   'bus_id': 'synthetic-bus', 'traffic_id': 'synthetic-traffic',
                   'activity': case.activity, 'bus_speed_mps': 2 if frame < 100 else 0,
                   'traffic_speed_mps': 3, 'loading_active': frame >= 150,
                   'right_front_wheel_xy': [5, case.target_distance_m],
                   'wheel_position_uncertainty_m': .001, 'bus_curb_angle_deg': 2}
            for name in ('frame', 'bus_motion', 'traffic_motion', 'right_front_wheel',
                         'curb_geometry', 'location_designation', 'loading_activity'):
                row[name + '_source_sha256'] = scene.get(name + '_source_sha256',
                                                           scene['bus_route_source_sha256'])
            rows.append(row)
        measured = measure_original(rows, scene, case)
        summaries.append({'case_id': scene['case_id'],
                          'source_kind': 'synthetic_diagnostic_fixture',
                          'physical_acceptance': False,
                          'legal_status': 'unresolved',
                          'measurement': measured})
    output = {'format': 'c149470-diagnostic-measurements-v1',
              'source_kind': 'synthetic_diagnostic_fixture',
              'physical_acceptance': False, 'cases': summaries}
    (HERE / 'diagnostic-measurements.json').write_text(
        json.dumps(output, indent=2) + '\n', encoding='utf-8')
    return output


if __name__ == '__main__':
    print('measured synthetic cases:', len(build()['cases']))
