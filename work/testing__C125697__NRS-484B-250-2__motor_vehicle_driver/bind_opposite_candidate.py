"""Bind the opposite diagnostic to an isolated assignment-root manifest."""
import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'cases/off_opposite_left_turn'
CASE = HERE.name + '__off_opposite_left_turn'


def build():
    manifest = json.loads((OUT / 'candidate-manifest.json').read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
    entry['construction'] = 'cases/off_opposite_left_turn/construction.json'
    entry['measurement_contract'] = 'cases/off_opposite_left_turn/measurement-contract.json'
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    if not any(CASE in row['case_ids'] for row in plan['requirement_dispositions']):
        for original in plan['requirement_dispositions'][:6]:
            row = copy.deepcopy(original)
            row['case_ids'] = [CASE]
            if row['requirement'].startswith('One identified median crossing'):
                row['requirement'] = 'One identified crossing with opposite approaches on the same highway'
                row['evidence_or_gap'] = 'Synthetic same-highway opposite lanes; public road identity and physical crossing remain unverified.'
            elif row['requirement'].startswith('The other vehicle is spatially right'):
                row['requirement'] = 'Relative approach side is measured while opposite direction is sourced'
                row['evidence_or_gap'] = 'Synthetic approach vectors face opposite directions; side measurement is descriptive only.'
            elif row['requirement'].startswith('Opposite-direction left-turn exception'):
                row['requirement'] = 'Opposite-direction left-turn intent and original motion/steering are retained'
                row['evidence_or_gap'] = 'Synthetic original frames show westbound-to-southbound turn; legal exception and physical motion unverified.'
            plan['requirement_dispositions'].append(row)
        plan_path.write_text(json.dumps(plan, indent=2, allow_nan=False) + '\n')
    contract_path = OUT / 'measurement-contract.json'
    contract = json.loads(contract_path.read_text())
    indices = [i for i, row in enumerate(plan['requirement_dispositions'])
               if CASE in row['case_ids']]
    if len(indices) != len(contract['requirements']):
        raise ValueError('Opposite case needs one disposition per measurement')
    for item, index in zip(contract['requirements'], indices):
        item['disposition_index'] = index
        item['requirement'] = plan['requirement_dispositions'][index]['requirement']
    contract_path.write_text(json.dumps(contract, indent=2, allow_nan=False) + '\n')
    proposals_path = HERE / 'proposals/cases.json'
    proposals = json.loads(proposals_path.read_text())
    if not any(row['case_id'] == CASE for row in proposals['cases']):
        proposal = copy.deepcopy(proposals['cases'][0])
        proposal['case_id'] = CASE
        proposal['target_type'] = 'exception_context_probe'
        proposal['rationale'] = ('Opposite directions on one synthetic highway with other vehicle '
                                 'turning westbound to southbound; no legal exclusion conclusion')
        proposal['recording_description'] = json.loads((OUT / 'config.json').read_text())['recording_description']
        proposal['paired_probe_id'] = 'c125697-opposite-left-turn-context'
        proposal['deliberate_differences'] = [
            'opposing lanes on one highway rather than perpendicular different-highway approaches',
            'other vehicle follows a westbound-to-southbound left-turn route']
        proposal['probe']['target_value_or_branch'] = 'off_opposite_left_turn'
        proposals['cases'].append(proposal)
        proposals_path.write_text(json.dumps(proposals, indent=2, allow_nan=False) + '\n')
    path = HERE / 'opposite-candidate-manifest.json'
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    return path


if __name__ == '__main__':
    print(build())
