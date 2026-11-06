"""Independent audit of unselected synthetic measurement receipts and controls."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE/'case-plan.json').read_text())
OUT = HERE/'draft-measurements'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    geometry_path = OUT/'native-geometry-draft.json'
    geometry = json.loads(geometry_path.read_text())
    assert geometry['native_center_lane_design_verified'] is False
    assert geometry['authored_map_sha256'] == digest(HERE/'draft-construction'/'scene.xodr')
    assert geometry['center_turn_lane_native_xy_bounds_m'][0]==-66.5
    assert geometry['left_turn_connector_road_id'] != geometry['highway_road_id']
    expected = ['within_50_feet', 'unresolved_at_50_feet', 'exceeds_50_feet']
    traces = []
    for case, relation in zip(PLAN['cases'], expected):
        stem = case['case_id'].rsplit('__', 1)[-1]
        samples_path = OUT/(stem+'-synthetic-native-samples.jsonl')
        receipt = json.loads((OUT/(stem+'-measurement.json')).read_text())
        rows = [json.loads(line) for line in samples_path.read_text().splitlines()]
        assert receipt['case_id'] == case['case_id']
        assert receipt['requested_setting_ft'] == case['requested_setting']
        assert receipt['draft_only'] is True and receipt['selected'] is False
        assert receipt['threshold_relation'] == relation
        assert receipt['left_turn_road_transition_frame_bracket'][1]<receipt['turn_completion_frame_bracket'][1]
        assert receipt['source_hashes'] == {samples_path.name:digest(samples_path),
                                            geometry_path.name:digest(geometry_path)}
        assert receipt['source_assignment_sha256'] == next(
            s['sha256'] for s in PLAN['sources'] if s['path'].endswith('/assignment.json'))
        assert receipt['authored_route_sha256'] == digest(HERE/'draft-construction'/f'route-{stem}.json')
        contract=json.loads((OUT/f'{stem}-contract.json').read_text())
        analysis=json.loads((OUT/f'{stem}-analysis-report.json').read_text())
        assert analysis['case_id']==case['case_id'] and analysis['draft_only'] is True
        assert analysis['selected'] is False
        assert {r['output_key'] for r in contract['requirements']}==set(analysis['measurements'])
        for item in analysis['measurements'].values():
            for name,checksum in item['sources'].items():
                expected_path=samples_path if name=='native_samples.jsonl' else geometry_path
                assert checksum==digest(expected_path)
        assert analysis['measurements']['after_left_turn_distance_interval']['value']['threshold_relation']==relation
        assert [r['native_frame'] for r in rows] == list(range(len(rows)))
        assert all(math.isclose(r['time_s'], i/20, abs_tol=1e-9) for i, r in enumerate(rows))
        assert all(r['native_road_id'] == 1 for r in rows[1:])
        assert all(r['native_forward_xy'] == [1,0] for r in rows[1:])
        assert rows[0]['native_road_id'] == 13 and rows[0]['native_forward_xy'] == [0,1]
        assert rows[-1]['native_lane_id'] == -2
        assert rows[1]['native_center_xy_m'] == [-66.5,0]
        lower, upper = receipt['distance_interval_m']
        assert lower <= receipt['sampled_distance_m'] <= upper
        if relation == 'within_50_feet': assert upper < 15.24
        if relation == 'exceeds_50_feet': assert lower > 15.24
        if relation == 'unresolved_at_50_feet': assert lower <= 15.24 <= upper
        traces.append((stem, rows, receipt))
    # The traces share all states until the first case starts its lateral
    # merge. Only the longitudinal merge trigger differs among drafts.
    minimum = min(len(rows) for _, rows, _ in traces) - 3
    for i in range(minimum):
        assert all(rows[i] == traces[0][1][i] for _, rows, _ in traces)
    print(json.dumps({'status':'synthetic_cpu_draft_audit_pass', 'cases':len(traces),
                      'common_prefix_frames':minimum,
                      'relations':[receipt['threshold_relation'] for _,_,receipt in traces]}, indent=2))


if __name__ == '__main__':
    audit()
