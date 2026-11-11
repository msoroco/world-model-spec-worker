"""Verify selected diagnostic cases and a required recording-channel guard."""
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from batch_pipeline.stages import validate


def check():
    plan = json.loads((FOLDER.parent / 'case-plan.json').read_text())
    selection = json.loads((FOLDER / 'semantic-selection.json').read_text())
    proposal = json.loads((FOLDER / 'cases-stage-proposal.json').read_text())
    inputs = json.loads((FOLDER / 'cases-stage-inputs.json').read_text())
    selected = set(selection['selected_cpu_diagnostic_cases'])
    pending = set(selection['pending_physical_cases'])
    planned = {case['case_id'] for case in plan['cases']}
    assert len(selected) == 3 and len(pending) == 6
    assert selected | pending == planned and not selected & pending
    assert {case['case_id'] for case in proposal['cases'] if case['target_type'] != 'baseline'} == selected
    validate('cases', copy.deepcopy(proposal), inputs)
    broken = copy.deepcopy(proposal)
    target = next(case for case in broken['cases'] if case['target_type'] != 'baseline')
    target['recording_description']['channels'] = [row for row in target['recording_description']['channels']
                                                  if row['name'] != 'time_to_conflict_s']
    try:
        validate('cases', broken, inputs)
    except ValueError as error:
        assert 'Recording omits required law observable/context: time_to_conflict_s' in str(error), str(error)
    else:
        raise AssertionError('Missing original time-to-conflict channel was accepted')
    return {'selected_cpu_diagnostic_cases': len(selected), 'pending_physical_cases': len(pending),
            'positive_cases_stage_valid': True, 'missing_recording_channel_rejected': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
