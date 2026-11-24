"""Draft exact controlled approach cases for the canonical cases stage."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    manifest = json.loads((HERE / 'current-execution-manifest.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    cases = []
    for entry in manifest['cases']:
        recording = json.loads((HERE / entry['construction']).read_text())['recording_description']
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        requested = ('continue_at_3_mps' if suffix == 'controlled_2' else
                     'right_edge_hold_without_607_verdict' if suffix == 'stopped_referral' else
                     'move_to_right_edge_and_stop_until_passed')
        official = suffix == 'official_approach'
        stopped = suffix == 'stopped_referral'
        cases.append({'case_id': entry['case_id'], 'target_law_id': plan['law_id'],
                      'target_type': 'judgment_sweep',
                      'rationale': ('Measure a moving emergency vehicle that stops; preserve the NRS 484B.607 referral without inferring its unsupplied duties.'
                                    if stopped else
                                    'Compare regulatory-agency official vehicle approach with the fixed emergency vehicle path and the same right-edge stop request; original agency identity remains for review.'
                                    if official else
                                    'Compare source-bound emergency approach, right-edge stop until passed, and continued travel; statutory qualification remains for original review.'),
                      'variable_assignments': {
                          'requested_subsection_1_response': {'kind': 'controller',
                                                       'value': requested,
                                                       'unit': 'categorical'},
                          'observed_emergency_approach': {'kind': 'subject_behavior',
                                                          'value': None, 'unit': 'boolean'},
                          'qualifying_source_vehicle_and_lamps': {'kind': 'world_setup',
                                                              'value': None,
                                                              'unit': 'boolean'},
                          'officer_direction': {'kind': 'world_setup', 'value': False,
                                                'unit': 'boolean'},
                          'responding_vehicle_kind': {'kind': 'world_setup',
                                                      'value': 'regulatory_agency_official' if official else 'authorized_emergency',
                                                      'unit': 'categorical'},
                          'source_vehicle_stops': {'kind': 'world_setup',
                                                   'value': stopped, 'unit': 'boolean'}},
                      'unresolved_judgment_calls': [
                          'authorized emergency or regulatory-agency vehicle with qualifying flashing lights',
                          'moving or visibly preparing to move',
                          'approaches the driver vehicle and invokes supplied subsection 1 duties',
                          'unless otherwise directed by a law enforcement officer'],
                      'paired_probe_id': HERE.name + ('__stopped_referral_comparison' if stopped else '__official_kind_comparison' if official else '__approach_response_pair'),
                      'deliberate_differences': ['source_vehicle_stops'] if stopped else ['responding_vehicle_kind'] if official else ['requested_subsection_1_response'],
                      'probe': {'primary_variable': 'source_vehicle_stops' if stopped else 'responding_vehicle_kind' if official else 'requested_subsection_1_response',
                                'comparison_or_standard': 'original source vehicle motion-to-stop time join' if stopped else 'original official agency source review with fixed response path' if official else 'source-bound right-edge geometry, stop-until-passed timing and continued travel',
                                'target_value_or_branch': True if stopped else 'regulatory_agency_official' if official else requested},
                      'recording_description': recording})
    proposal = {'cell_id': plan['cell_id'], 'actor': plan['actor'], 'status': 'draft',
                'sweeps_expanded': True, 'sweep_specs': [], 'cases': cases}
    target = HERE / 'proposals/cases.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'selected_cases': len(cases), 'proposal': target.relative_to(HERE).as_posix()}))


if __name__ == '__main__':
    main()
