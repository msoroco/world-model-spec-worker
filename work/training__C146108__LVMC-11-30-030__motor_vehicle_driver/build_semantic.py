"""Source-hashed original-law semantic proposals; legal judgment stays open."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
OUT = HERE / 'proposals'
ASSIGNMENT = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
LAW, CELL, ACTOR = (ASSIGNMENT[k] for k in ('law_id', 'cell_id', 'actor'))
QUOTE = ASSIGNMENT['law']['text']
TEMPLATE = LAW + '@' + ACTOR


def write(name, value):
    OUT.mkdir(exist_ok=True)
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    return {'path': str(path.relative_to(HERE)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def reference(name):
    path = OUT / (name + '.json')
    return {'path': str(path.relative_to(HERE)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def observable(phrase, note, name, source):
    return {'template_id': TEMPLATE, 'phrase': phrase, 'note': note, 'status': 'draft',
        'observable_requirements': {
            'observables': [{'name': name, 'unit': 'structured',
                'description': 'Original 600-frame Native actor bodies and four-camera time join.'}],
            'context_inputs': [{'name': source, 'unit': 'structured',
                'description': 'Original crossing/stop-purpose source and independent full-interval review.'}],
            'sweep_dimensions': [{'name': name, 'unit': 'category',
                'description': 'Controlled crossing-kind or pass-policy request, not legal classification.'}],
            'landmarks': [],
            'recording_needs': [{'name': name, 'unit': 'structured',
                'description': 'Original synchronized crossing, lead, pedestrian, ego and camera source.'}],
            'limitations': ['Authored geometry and scripted stop do not establish crossing identity or stop purpose.']}}


def main():
    relevance = {'actor': ACTOR, 'cell_id': CELL, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': QUOTE, 'applies_to': [ACTOR],
            'relevance_type': 'direct', 'confidence': 'high',
            'notes': 'Frozen one-way overtaking cell; crossing identity and stop purpose need original review.'}],
        'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance-batch', relevance), 'relevance': write('relevance', relevance)}
    judgments = [
        ('stopped at a marked crosswalk or at any unmarked crosswalk at an intersection',
         'Original map and crossing review must establish the marked or unmarked intersection reference.',
         'st.crosswalk', 'crosswalk_reference'),
        ('to permit a pedestrian to cross the roadway',
         'Lead rest and pedestrian proximity alone do not establish the purpose of the stop.',
         'ru.pedestrian', 'lead_body'),
        ('any other vehicle approaching from the rear',
         'Original Native ego/lead directions and full bodies must establish rear approach.',
         'drv.approaching', 'ego_body'),
        ('shall not overtake and pass such stopped vehicle',
         'Measure adjacent longitudinal overlap and getting ahead during crossing; do not infer legal outcome from a controller request.',
         'rel.longitudinal_overlap', 'camera_manifest')]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR, 'quote': QUOTE,
        'status': 'draft', 'structure': {
            'activation': {'description': 'A vehicle stopped at a marked or unmarked intersection crosswalk to permit pedestrian crossing, with another vehicle approaching from rear',
                'source_clause': 'Whenever any vehicle is stopped at a marked crosswalk or at any unmarked crosswalk at an intersection to permit a pedestrian to cross the roadway'},
            'obligation': {'description': 'The rear approaching driver shall not overtake and pass the stopped vehicle',
                'type': 'must_not', 'source_clause': 'the driver of any other vehicle approaching from the rear shall not overtake and pass such stopped vehicle'},
            'exceptions': [], 'timing': {'description': 'Continuous stopped-lead and pedestrian crossing interval; no numeric legal cutoff'},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note, _, _ in judgments]},
        'parameter_refs': [{'name': 'crosswalk_kind_request', 'kind': 'world_setup',
                            'range_or_domain': ['marked', 'unmarked_intersection']},
                           {'name': 'overtake_pass_policy', 'kind': 'controller',
                            'range_or_domain': [False, True]}]}
    refs['template'] = write('template', template)
    refs['judgment_observables'] = [write('judgment_observables_' + str(i),
        observable(phrase, note, name, source)) for i, (phrase, note, name, source) in enumerate(judgments, 1)]
    binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [{'name': 'one_way_rear_approach_request',
            'source': 'frozen one-way overtaking cell and authored crossing/readback request'}],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [{'name': 'crosswalk_kind_request', 'kind': 'world_setup',
            'range_or_domain': ['marked', 'unmarked_intersection'], 'used_by_laws': [LAW]},
            {'name': 'overtake_pass_policy', 'kind': 'controller',
             'range_or_domain': [False, True], 'used_by_laws': [LAW]}]}
    refs['bindings'] = write('bindings', binding)
    cases_path = OUT / 'cases.json'
    cases = json.loads(cases_path.read_text())
    cases['sweep_specs'][0]['judgment_refs'] = template['structure']['judgment_calls_needed']
    cases_path.write_text(json.dumps(cases, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    refs['cases'] = reference('cases')
    (OUT / 'semantic-index.json').write_text(json.dumps({'assignment_id': AID,
        'format': 'worker-semantic-delivery', 'stages': refs}, indent=2, ensure_ascii=False) + '\n')
    return {'selected_cases': 4, 'judgment_observables': len(judgments),
            'index_sha256': hashlib.sha256((OUT / 'semantic-index.json').read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
