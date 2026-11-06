"""Independent unselected no-countdown engineering plan and comparison audit."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
summary = json.loads((HERE / 'no-countdown-summary.json').read_text())
plans = {}
for suffix in ('controlled_1', 'controlled_2'):
    values = []
    for ident in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        path = HERE / 'draft-candidates' / suffix / ident / 'construction.json'
        plan = json.loads(path.read_text())
        assert plan['case_id'].endswith('__' + suffix)
        assert plan['candidate_id'] == ident
        assert (plan['law_id'], plan['cell_id'], plan['actor'], plan['duration_s'], plan['rate_hz']) == (
            'NRS-484B-283-1d3', 'C10316', 'pedestrian', 12, 20)
        assert plan['crosswalk_id'] == 'C10316-authored-alley-crosswalk'
        assert plan['comparison_variable'] == 'no_countdown_flash_start_s'
        assert plan['status'].startswith('unselected_')
        assert plan['engineering']['steady_start_s'] == 9
        assert (plan['engineering']['display_camera_width'], plan['engineering']['display_camera_height']) == (1280, 720)
        values.append(plan)
    assert len({json.dumps(item['engineering'], sort_keys=True) for item in values}) == 4
    assert len({(item['case_id'], item['law_id'], item['cell_id'], item['actor'],
                 item['duration_s'], item['rate_hz'], item['road_source']) for item in values}) == 1
    assert values[1]['engineering']['spawn_start_x_m'] == -6.5
    assert values[2]['engineering']['clock_mode'] == 'snapshot_timestamp_20hz'
    assert values[3]['engineering']['display_camera_distance_m'] == 3.5
    assert len({value['trigger']['metric'] for value in values[1:]}) == 3
    plans[suffix] = values

for first, second in zip(plans['controlled_1'], plans['controlled_2']):
    assert first['candidate_id'] == second['candidate_id']
    assert first['engineering']['flash_start_s'] == 2.0
    assert second['engineering']['flash_start_s'] == .5
    assert {key: value for key, value in first['engineering'].items() if key != 'flash_start_s'} == {
        key: value for key, value in second['engineering'].items() if key != 'flash_start_s'}

for record in summary['records']:
    rows = [json.loads(line) for line in (Path(record['retained_positive']) / 'no-countdown-samples.jsonl').read_text().splitlines()
            if line.strip()]
    clearance = -3.5 - max(point[0] for point in rows[0]['pedestrian_footprint_xy_m'])
    assert round(clearance, 3) == .88
print(json.dumps({'unselected_candidate_plans': 8, 'distinct_fallbacks_per_case': 3,
                  'controlled_difference': 'flash_start_s', 'synthetic_spawn_clearance_m': .88,
                  'physically_measured_triggers': 0, 'selected_cases': 0}))
