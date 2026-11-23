"""Author source-bound draft semantic stages for the 15-foot projection rule."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent
ROOT = PACKAGE.parents[1]
ASSIGNMENT = PACKAGE.name
PROPOSALS = PACKAGE / 'proposals'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    original = json.loads((ROOT / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
    plan = json.loads((PACKAGE / 'case-plan.json').read_text())
    manifest = json.loads((PACKAGE / 'draft-primary-manifest.json').read_text())
    law_id, cell_id, actor = (original[key] for key in ('law_id', 'cell_id', 'actor'))
    quote = original['law']['text']
    template_id = law_id + '@' + actor
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law_id, 'quote': quote,
                                    'applies_to': [actor], 'relevance_type': 'specific_match',
                                    'confidence': 'medium',
                                    'notes': 'The frozen cell concerns a parked vehicle projecting into the street; original curb and attachment context still needs Native review.'}],
                 'borderline_excluded': []}
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
                'status': 'draft', 'quote': quote,
                'structure': {
                    'activation': {'description': 'A vehicle, its load or attached trailer projects into the street from a curb.',
                                   'source_clause': 'any part of any vehicle, part of the load of such vehicle or trailer attached to such vehicle'},
                    'obligation': {'type': 'must_not',
                                   'description': 'Do not project more than fifteen feet into the street, measured at right angles to the curb.',
                                   'source_clause': 'project into the street more than fifteen feet measured on a line at right angles to the curb',
                                   'numeric_conditions': [{'variable': 'observed_projection_perpendicular_to_curb_ft',
                                                           'operator': '>', 'value': 15, 'unit': 'ft'}]},
                    'exceptions': [],
                    'timing': {'description': 'Apply to the retained parked interval and its maximum full-part projection.'},
                    'judgment_calls_needed': []},
                'parameter_refs': [
                    {'name': 'commanded_projection_perpendicular_to_curb_ft',
                     'kind': 'controller', 'range_or_domain': 'authored 14, 15 or 16 foot target; actual geometry requires Native verification'},
                    {'name': 'observed_projection_perpendicular_to_curb_ft',
                     'kind': 'subject_behavior', 'range_or_domain': 'source-derived maximum over vehicle, load and trailer; unknown before original capture'}]}
    bindings = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                'established_contexts': [{'name': 'parked_vehicle_curb_projection',
                                          'source': 'frozen catalog cell and exact law text'}],
                'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
                'context_refs': [], 'fixed_parameters': [],
                'variable_parameters': [
                    {'name': 'commanded_projection_perpendicular_to_curb_ft',
                     'kind': 'controller', 'range_or_domain': '14, 15 or 16 ft authored target',
                     'used_by_laws': [law_id]},
                    {'name': 'observed_projection_perpendicular_to_curb_ft',
                     'kind': 'subject_behavior', 'range_or_domain': 'original Native full-part curb-normal maximum in ft',
                     'used_by_laws': [law_id]}]}
    entries = {entry['case_id']: entry for entry in manifest['cases']}
    selected = []
    for planned in plan['cases']:
        case_id = planned['case_id']
        entry = entries[case_id]
        construction = json.loads((PACKAGE / entry['construction']).read_text())
        target = planned['requested_setting']
        epsilon = {'value': 1, 'unit': 'ft',
                   'rationale': 'Authored diagnostic spacing around the exact statutory 15-foot boundary; not a legal tolerance.'}
        selected.append({'case_id': case_id, 'target_law_id': law_id,
                         'target_type': 'boundary_probe',
                         'rationale': 'Source-derived diagnostic boundary; original curb, attachments and physical extent require Native review.',
                         'variable_assignments': {
                             'commanded_projection_perpendicular_to_curb_ft': {'kind': 'controller', 'value': target, 'unit': 'ft'},
                             'observed_projection_perpendicular_to_curb_ft': {'kind': 'subject_behavior', 'value': None, 'unit': 'ft'}},
                         'unresolved_judgment_calls': [],
                         'recording_description': construction['recording_description'],
                         'paired_probe_id': plan['comparisons'][0]['comparison_id'],
                         'deliberate_differences': ['commanded_projection_perpendicular_to_curb_ft'],
                         'epsilon_used': epsilon,
                         'probe': {'primary_variable': 'commanded_projection_perpendicular_to_curb_ft',
                                   'comparison_or_standard': 'exact greater-than-15-foot statutory projection boundary',
                                   'target_value_or_branch': target,
                                   'threshold_ref': 'obligation.numeric_conditions[0]',
                                   'operator': '>', 'unit': 'ft', 'test_value': target}})
    baseline_recording = selected[1]['recording_description']
    baseline = {'case_id': ASSIGNMENT + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Shared neutral authored curb and actor context; no original evidence is claimed.',
                'variable_assignments': {
                    'commanded_projection_perpendicular_to_curb_ft': {'kind': 'controller', 'value': 15, 'unit': 'ft'},
                    'observed_projection_perpendicular_to_curb_ft': {'kind': 'subject_behavior', 'value': None, 'unit': 'ft'}},
                'unresolved_judgment_calls': [],
                'recording_description': baseline_recording}
    cases = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
             'sweep_specs': [], 'cases': [baseline, *selected]}
    for name, value in (('relevance_batch', relevance), ('relevance', relevance),
                        ('template', template), ('bindings', bindings), ('cases', cases)):
        write(PROPOSALS / (name + '.json'), value)
    stages = {name: {'path': 'proposals/' + name + '.json',
                     'sha256': sha(PROPOSALS / (name + '.json'))}
              for name in ('relevance_batch', 'relevance', 'template', 'bindings', 'cases')}
    stages['judgment_observables'] = []
    write(PROPOSALS / 'semantic-index.json',
          {'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
           'stages': stages, 'status': 'draft', 'original_native_observed': False})
    print(json.dumps({'semantic_stage_files': 5, 'selected_case_proposals': len(selected),
                      'semantic_index_sha256': sha(PROPOSALS / 'semantic-index.json')}))


if __name__ == '__main__':
    main()
