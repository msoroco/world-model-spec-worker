"""Draft exact controlled approach cases for the canonical cases stage."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    manifest = json.loads((HERE / 'current-execution-manifest.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    recording = json.loads((HERE / manifest['cases'][0]['construction']).read_text())['recording_description']
    cases = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        requested = 'reduce_to_1_mps' if suffix == 'controlled_1' else 'continue_at_3_mps'
        cases.append({'case_id': entry['case_id'], 'target_law_id': plan['law_id'],
                      'target_type': 'judgment_sweep',
                      'rationale': 'Compare source-bound emergency approach and subject speed response; subsection 1 duties and qualification remain for original review.',
                      'variable_assignments': {
                          'requested_speed_response': {'kind': 'controller',
                                                       'value': requested,
                                                       'unit': 'categorical'},
                          'observed_emergency_approach': {'kind': 'subject_behavior',
                                                          'value': None, 'unit': 'boolean'},
                          'qualifying_emergency_and_lamps': {'kind': 'world_setup',
                                                              'value': None,
                                                              'unit': 'boolean'},
                          'officer_direction': {'kind': 'world_setup', 'value': False,
                                                'unit': 'boolean'}},
                      'unresolved_judgment_calls': [
                          'authorized emergency or regulatory-agency vehicle with qualifying flashing lights',
                          'moving or visibly preparing to move',
                          'approaches the driver vehicle and invokes supplied subsection 1 duties',
                          'unless otherwise directed by a law enforcement officer'],
                      'paired_probe_id': HERE.name + '__approach_response_pair',
                      'deliberate_differences': ['requested_speed_response'],
                      'probe': {'primary_variable': 'requested_speed_response',
                                'comparison_or_standard': 'source-bound post-approach ego speed and closing geometry',
                                'target_value_or_branch': requested},
                      'recording_description': recording})
    proposal = {'cell_id': plan['cell_id'], 'actor': plan['actor'], 'status': 'draft',
                'sweeps_expanded': True, 'sweep_specs': [], 'cases': cases}
    target = HERE / 'proposals/cases.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'selected_cases': len(cases), 'proposal': target.relative_to(HERE).as_posix()}))


if __name__ == '__main__':
    main()
