"""Independent source and controlled-pair audit of the draft cases proposal."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    proposal = json.loads((HERE / 'proposals/cases.json').read_text())
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    assert proposal['cell_id'] == plan['cell_id'] == 'C104538'
    assert proposal['actor'] == plan['actor'] == 'motor_vehicle_driver'
    assert proposal['status'] == 'draft'
    authored = {row['case_id']: row for row in plan['cases']}
    proposed = {row['case_id']: row for row in proposal['cases']}
    bundled = {row['case_id']: row for row in manifest['cases']}
    assert len(authored) == len(proposed) == len(bundled) == 3
    assert set(authored) == set(proposed) == set(bundled)
    assert sorted(row['requested_setting'] for row in authored.values()) == [450, 500, 550]
    for case_id, row in proposed.items():
        planned = authored[case_id]
        assert row['target_law_id'] == plan['law_id'] == 'NRS-484B-407'
        assert row['target_type'] == planned['target_type']
        assignments = row['variable_assignments']
        assert assignments['authored_sightline_limit_ft'] == {
            'kind': 'environment', 'value': planned['requested_setting'], 'unit': 'ft'}
        assert assignments['observed_two_direction_body_visibility']['value'] is None
        assert row['unresolved_judgment_calls']
        construction = json.loads((HERE / bundled[case_id]['construction']).read_text())
        assert row['recording_description'] == construction['recording_description']
    comparison = plan['comparisons'][0]
    assert len(proposal['sweep_specs']) == 1
    sweep = proposal['sweep_specs'][0]
    assert sweep['comparison_id'] == comparison['comparison_id']
    assert sweep['case_ids'] == comparison['case_ids']
    assert sweep['values_ft'] == [authored[case_id]['requested_setting']
                                  for case_id in sweep['case_ids']]
    assert sweep['status'] == 'planned_unverified'
    print(json.dumps({'cases': 3, 'controlled_sweeps': 1,
                      'selected': 0, 'original_visibility_observed': 0}))


if __name__ == '__main__':
    main()
