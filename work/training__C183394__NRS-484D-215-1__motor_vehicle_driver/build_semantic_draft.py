"""Source-grounded canonical stage drafts; cases need threshold expansion."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = next(parent for parent in ROOT.parents if (parent / 'batch.json').is_file())
assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
LAW = assignment['law']
ACTOR = assignment['actor']
TEMPLATE = LAW['id'] + '@' + ACTOR
OUT = ROOT / 'proposals'


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


relevance = {'cell_id': assignment['cell_id'], 'actor': ACTOR, 'status': 'draft',
             'relevant_laws': [{'law_id': LAW['id'], 'quote': LAW['text'],
                 'applies_to': [ACTOR], 'relevance_type': 'specific_duty',
                 'confidence': 'medium',
                 'notes': 'Adjacent paved shoulder and opposed vehicle are authored; qualifying highway, incorporated lighting time and optical outcomes need original review.'}],
             'borderline_excluded': []}
write('relevance_batch.json', relevance)
write('relevance.json', relevance)

judgments = [
    ('safe distance in advance of the vehicle', 'No numeric safe-distance substitute; original forward person/vehicle illumination requires independent review.', 'env.visibility'),
    ('glaring rays are not projected into the eyes of the oncoming driver', 'Original driver-eye light rays and pixels need independent review; lamp API bit is insufficient.', 'sig.headlamp'),
    ('lowermost distribution of light, or composite beam, specified in subsection 2 of NRS 484D.210', 'Equipment specifications are unavailable; do not invoke statutory deeming without their source.', 'sig.headlamp')]
structure = {'activation': {'condition': 'Motor vehicle operated on traveled highway or adjacent shoulder during one of the times specified in incorporated NRS 484D.100.', 'numeric_conditions': []},
             'obligation': {'type': 'must', 'description': 'Reveal persons and vehicles ahead at a safe distance with sufficient illumination and, when approaching within 500 feet, avoid glaring rays in the oncoming driver eyes.',
                            'source_clause': 'the driver shall use a distribution of light, or composite beam',
                            'numeric_conditions': [{'variable': 'oncoming_centre_distance_ft', 'operator': '<=', 'value': 500, 'unit': 'ft'}]},
             'exceptions': [{'trigger': 'Exact statutory lowermost distribution under NRS 484D.210(2)',
                             'effect': 'Deemed to avoid glare regardless of contour and loading only if exact equipment identity is established.',
                             'replacement_obligation': 'Forward illumination duty remains.',
                             'source_clause': 'The lowermost distribution of light, or composite beam, specified in subsection 2 of NRS 484D.210 [DEF-NRS-484D-210-1-2] shall be deemed to avoid glare at all times, regardless of road contour and loading.'}],
             'timing': {'description': 'Lighting duty during incorporated NRS 484D.100 times; avoid glare throughout observed approach at or inside 500 feet.', 'numeric_conditions': []},
             'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note, _ in judgments]}
write('template.json', {'template_id': TEMPLATE, 'law_id': LAW['id'], 'actor': ACTOR,
                        'status': 'draft', 'quote': LAW['text'], 'structure': structure,
                        'parameter_refs': [{'name': 'oncoming_centre_distance_ft', 'kind': 'subject_behavior', 'range_or_domain': 'Original pairwise measured centre separation across 500 feet'},
                                           {'name': 'beam_request_policy', 'kind': 'controller', 'range_or_domain': 'dim before 500-foot entry or retain high beam'}]})
for index, (phrase, note, channel) in enumerate(judgments):
    write('judgment_observables_' + str(index) + '.json',
          {'template_id': TEMPLATE, 'phrase': phrase, 'note': note, 'status': 'draft',
           'observable_requirements': {
               'observables': [{'name': channel, 'unit': 'structured', 'description': note}],
               'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
               'recording_needs': [{'name': channel, 'unit': 'structured', 'description': note}],
               'limitations': [note]}})
write('bindings.json', {'cell_id': assignment['cell_id'], 'actor': ACTOR, 'status': 'draft',
       'established_contexts': [{'name': 'paved_shoulder_opposed_vehicle', 'source': 'frozen catalog C183394 and original Native construction'}],
       'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}], 'context_refs': [],
       'fixed_parameters': [{'name': 'cell_paved_shoulder', 'value': True, 'rationale': 'Frozen cell layout'}],
       'variable_parameters': [
           {'name': 'oncoming_centre_distance_ft', 'kind': 'subject_behavior',
            'range_or_domain': 'Original measured centre separation, including below/at/above 500 feet', 'used_by_laws': [LAW['id']]},
           {'name': 'beam_request_policy', 'kind': 'controller',
            'range_or_domain': 'dim_within_500 or retain_high', 'used_by_laws': [LAW['id']]}]})
