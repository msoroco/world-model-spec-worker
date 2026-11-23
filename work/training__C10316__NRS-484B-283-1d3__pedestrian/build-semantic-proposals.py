"""Build source-bound draft semantic stages without a legal verdict."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.name
LAW = 'NRS-484B-283-1d3'


def write(name, value):
    path = HERE / 'proposals' / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    quote = plan['source_law']['text']
    assert hashlib.sha256(quote.encode()).hexdigest() == plan['source_law']['text_sha256']
    assert 'flashing but is not accompanied by a countdown timer' in quote
    assert 'before the “Don’t Walk”' in quote
    case_ids = [case['case_id'] for case in plan['cases']]
    assert len(case_ids) == 2
    relevance = {
        'cell_id': 'C10316', 'actor': 'pedestrian', 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': quote,
                           'applies_to': ['pedestrian'], 'relevance_type': 'specific_match',
                           'confidence': 'medium',
                           'notes': 'The crosswalk cell and requested no-countdown signal match the clause; original governing display and exceptions are unverified.'}],
        'borderline_excluded': []}
    template = {
        'template_id': LAW + '@pedestrian', 'law_id': LAW, 'actor': 'pedestrian',
        'status': 'draft', 'quote': quote,
        'structure': {
            'activation': {'condition': 'A pedestrian faces a governing pedestrian signal flashing Don’t Walk or Wait without a countdown timer.',
                           'numeric_conditions': []},
            'obligation': {'type': 'conditional',
                           'description': 'A pedestrian may not proceed to cross during the no-countdown flashing indication. A pedestrian who entered lawfully under subparagraph (1) may continue, but must reach a listed place of safety before the indication becomes steady.',
                           'source_clause': quote.split('While the ', 1)[1],
                           'numeric_conditions': []},
            'exceptions': [
                {'source': 'NRS 484B.287', 'status': 'requires_independent_context_review'},
                {'source': 'NRS 484B.290', 'status': 'requires_independent_context_review'},
                {'source': 'NRS 484B.350', 'status': 'requires_independent_context_review'},
                {'source': 'NRS 484B.283(1)(d)(1)', 'status': 'lawful_prior_entry_dependency'}],
            'timing': {'description': 'Distinguish first highway entry during Walk from new first entry during flashing; for a lawful prior entrant, compare full-body arrival at a listed safety place with onset of steady indication.',
                       'numeric_conditions': []},
            'judgment_calls_needed': ['whether the actual display governs the pedestrian direction',
                                      'whether prior entry was lawful under subparagraph (1)',
                                      'whether a cited introductory exception applies',
                                      'whether the destination is a listed place of safety']},
        'parameter_refs': [
            {'name': 'flash_start_s', 'kind': 'world_setup', 'range_or_domain': 'requested 2.0 s versus 0.5 s; engineering setting only'},
            {'name': 'original_signal_history', 'kind': 'source_observation', 'range_or_domain': 'original governing pixels, native timestamps and countdown presence'},
            {'name': 'first_highway_entry', 'kind': 'subject_behavior', 'range_or_domain': 'first original full-body footprint contact with surveyed highway'},
            {'name': 'full_body_safety_arrival', 'kind': 'subject_behavior', 'range_or_domain': 'original footprint at curb, sidewalk, safety zone if present, or other reviewed safety place'}]}
    bindings = {
        'cell_id': 'C10316', 'actor': 'pedestrian', 'status': 'draft',
        'established_contexts': [{'name': 'C10316-crosswalk-cell', 'source': 'frozen catalog C10316'}],
        'law_refs': [{'template_id': template['template_id'], 'binding_kind': 'direct'}],
        'context_refs': [{'source': ref, 'status': 'unresolved'} for ref in
                         ('NRS 484B.287', 'NRS 484B.290', 'NRS 484B.350', 'NRS 484B.283(1)(d)(1)')],
        'fixed_parameters': ['C10316 cell', 'pedestrian route and body controller', '12 s at 20 Hz',
                             'four camera profile', 'steady start at 9 s'],
        'variable_parameters': [{'name': 'flash_start_s', 'kind': 'world_setup',
                                 'range_or_domain': '2.0 s or 0.5 s requested',
                                 'used_by_laws': [LAW]}]}
    for name, obj in [('relevance_batch.json', relevance), ('relevance.json', relevance),
                      ('template.json', template), ('bindings.json', bindings)]:
        write(name, obj)
    stages = {key: write(key + '.json', obj) for key, obj in
              [('relevance_batch', relevance), ('relevance', relevance),
               ('template', template), ('bindings', bindings)]}
    stages['cases'] = {'path': 'proposals/cases.json',
                       'sha256': hashlib.sha256((HERE / 'proposals/cases.json').read_bytes()).hexdigest()}
    stages['judgment_observables'] = [
        {'name': name, 'status': 'original_native_required'} for name in
        ('governing_display_pixels', 'countdown_absence', 'lawful_walk_entry',
         'full_body_safety_arrival', 'introductory_exception_context')]
    index = {'format': 'worker-semantic-delivery', 'assignment_id': BASE,
             'stages': stages, 'status': 'draft', 'original_native_observed': False,
             'legal_verdict_claimed': False}
    write('semantic-index.json', index)
    return {'stages': list(stages), 'source_text_sha256': plan['source_law']['text_sha256'],
            'case_ids': case_ids, 'status': 'draft'}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
