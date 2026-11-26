"""Bind the exact taxi pair to a canonical cases-stage proposal."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
AID = BASE.name


def main():
    selected = json.loads((BASE / 'selected-draft-manifest.json').read_text())
    plan = json.loads((BASE / 'case-plan.json').read_text())
    assert {c['case_id'] for c in selected['cases']} == {c['case_id'] for c in plan['cases']}
    cases = []
    reference = json.loads((BASE / 'selected-probe_a-construction.json').read_text())
    cases.append({
        'case_id': AID + '__baseline', 'target_law_id': None,
        'target_type': 'baseline',
        'rationale': 'Shared outside-stand taxi stop before the requested loading subject varies.',
        'variable_assignments': {
            'curb_and_stand_context': {
                'kind': 'world_setup',
                'value': 'same source-reviewed street, curb and stand boundary'},
            'taxi_and_participant': {
                'kind': 'world_setup',
                'value': 'same taxi and participant actor identities'},
            'loading_subject_and_occupant_transition': {
                'kind': 'controller', 'value': None}},
        'unresolved_judgment_calls': [
            'taxicab stand so designated',
            'temporarily stopping in accordance with other regulations',
            'actually engaged in expeditious loading or unloading of passengers'],
        'recording_description': reference['recording_description']})
    for suffix, activity in [('probe_a', 'passenger_loading'),
                             ('probe_b', 'merchandise_loading')]:
        case_id = AID + '__' + suffix
        construction_path = BASE / ('selected-' + suffix + '-construction.json')
        construction = json.loads(construction_path.read_text())
        cases.append({
            'case_id': case_id,
            'target_law_id': 'LVMC-11-60-040',
            'target_type': 'judgment_sweep',
            'rationale': ('Observe source-reviewed ' + activity.replace('_', ' ') +
                          ' during the same outside-stand taxi stop.'),
            'variable_assignments': {
                'curb_and_stand_context': {
                    'kind': 'world_setup',
                    'value': 'same source-reviewed street, curb and stand boundary'},
                'taxi_and_participant': {
                    'kind': 'world_setup',
                    'value': 'same taxi and participant actor identities'},
                'loading_subject_and_occupant_transition': {
                    'kind': 'controller', 'value': activity}},
            'unresolved_judgment_calls': [
                'taxicab stand so designated',
                'temporarily stopping in accordance with other regulations',
                'actually engaged in expeditious loading or unloading of passengers'],
            'recording_description': construction['recording_description'],
            'paired_probe_id': 'c394327-passenger-merchandise-pair',
            'deliberate_differences': ['loading_subject_and_occupant_transition'],
            'probe': {'primary_variable': 'loading_subject_and_occupant_transition',
                      'comparison_or_standard': 'original source-reviewed passenger versus merchandise activity',
                      'target_value_or_branch': activity}})
    proposal = {'cell_id': 'C394327', 'actor': 'taxi_driver', 'status': 'draft',
                'cases': cases, 'sweep_specs': [{
                    'sweep_id': 'taxi_stop_exception_source_review',
                    'target_law_id': 'LVMC-11-60-040',
                    'judgment_refs': [
                        {'phrase': 'taxicab stand so designated',
                         'note': 'Original stand designation and street position require authority review.'},
                        {'phrase': 'temporarily stopping in accordance with other regulations',
                         'note': 'Original stop duration and other parking-rule authority require review.'},
                        {'phrase': 'actually engaged in expeditious loading or unloading of passengers',
                         'note': 'Original participant activity and continuous loading interval require review.'}],
                    'status': 'incomplete',
                    'rationale': 'Qualitative authority and activity judgments require original source review before a physical sweep can be finalized.',
                    'missing_inputs': [
                        'Original stand designation and other stopping rules',
                        'Original taxi and participant activity and duration evidence']}],
                'sweeps_expanded': True}
    out = BASE / 'proposals' / 'cases.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
