"""Independent fixture/source and controlled-input audit for C10052."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'draft-facility'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit():
    plan = json.loads((HERE/'case-plan.json').read_text())
    source = json.loads((ROOT/'inputs'/HERE.name/'assignment.json').read_text())
    assert plan['statutory_text'] == source['law_record']['text']
    assert plan['sources'][0]['sha256'] == sha(ROOT/'inputs'/HERE.name/'assignment.json')
    summary = json.loads((OUT/'summary.json').read_text())
    assert summary['selected'] is False and summary['ready'] is False
    assert {r['case_suffix'] for r in summary['rows']} == {'probe_a', 'probe_b'}
    reviewed = {}
    for suffix, expected_y, expected_overlap in (('probe_a', -1.5, 0.0),
                                                  ('probe_b', -4.0, 9.36)):
        folder = OUT/suffix
        data = rows(folder/'native_samples.jsonl')
        geometry = json.loads((folder/'road_geometry.json').read_text())
        context = json.loads((folder/'exception_context.json').read_text())
        receipt = json.loads((folder/'measurement.json').read_text())
        contract = json.loads((folder/'measurement-contract.json').read_text())
        contract_report = json.loads((folder/'contract-report.json').read_text())
        saved_report = json.loads((folder/'saved-analysis-report.json').read_text())
        assert len(data) == receipt['original_frames'] == 480
        assert receipt['source_sha256'] == {
            name: sha(folder/name) for name in
            ('native_samples.jsonl', 'road_geometry.json', 'exception_context.json')}
        assert contract['case_id'] == next(c['case_id'] for c in plan['cases']
                                            if c['case_id'].endswith('__'+suffix))
        assert {r['disposition_index'] for r in contract['requirements']} == {0}
        assert contract['negative'] == {
            'remove': ['exception_context.json'],
            'error_contains': 'Missing required source: exception_context.json'}
        for report in (contract_report, saved_report):
            observation = report['measurements']['facility_stop_observation']
            assert observation['sources'] == receipt['source_sha256']
            assert observation['value']['max_stopped_overlap_m2'] == expected_overlap
            assert observation['value']['observed_exception_status'] == 'unresolved'
        assert geometry['native_facility_design_verified'] is False
        assert context['source_kind'] == 'synthetic_scene_request'
        assert set(context['exceptions']) == {
            'entering_or_exiting_alley_or_driveway', 'disabled_vehicle',
            'avoiding_traffic_conflict', 'official_duties', 'police_direction', 'emergency'}
        assert all(value is False for value in context['exceptions'].values())
        assert receipt['observed_exception_status'] == 'unresolved'
        assert receipt['yield_duty_measured'] is False
        assert receipt['legal_verdict_claimed'] is False
        assert receipt['native_facility_design_verified'] is False
        assert data[-1]['native_center_xy_m'] == [-12.0, expected_y]
        assert receipt['max_stopped_overlap_m2'] == expected_overlap
        assert receipt['mean_stopped_overlap_m2'] == expected_overlap
        assert receipt['stop_duration_s'] >= 2.0
        for i, row in enumerate(data):
            assert row['native_frame'] == 100+i
            assert abs(row['time_s'] - (i+1)/20) < 1e-10
            assert row['native_road_id'] == 1
            x, y = row['native_center_xy_m']
            fx, fy = row['native_forward_xy']
            expected = [[x+long*fx-side*fy, y+long*fy+side*fx]
                        for long, side in ((-2.6, -.9), (-2.6, .9),
                                           (2.6, .9), (2.6, -.9))]
            assert row['native_body_xy_m'] == expected
        reviewed[suffix] = data
    assert json.loads((OUT/'probe_a/road_geometry.json').read_text()) == json.loads(
        (OUT/'probe_b/road_geometry.json').read_text())
    assert json.loads((OUT/'probe_a/exception_context.json').read_text()) == json.loads(
        (OUT/'probe_b/exception_context.json').read_text())
    for a, b in zip(reviewed['probe_a'][:61], reviewed['probe_b'][:61]):
        assert a == b
    result = {'format': 'c10052-independent-synthetic-pair-audit-v1',
              'source_law_sha256': hashlib.sha256(plan['statutory_text'].encode()).hexdigest(),
              'shared_prefix_frames': 61, 'outside_stopped_overlap_m2': 0.0,
              'inside_stopped_overlap_m2': 9.36,
              'exception_status': 'unresolved', 'physical_native_claim': False,
              'legal_verdict_claim': False}
    (OUT/'independent-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
