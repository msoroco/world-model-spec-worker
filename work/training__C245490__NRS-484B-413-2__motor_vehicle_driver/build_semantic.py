"""Draft exact-law semantic proposals; no physical or legal verdict."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / 'proposals'
ASSIGNMENT = json.loads((REPO / 'inputs' / HERE.name / 'assignment.json').read_text())
LAW, CELL, ACTOR = (ASSIGNMENT[key] for key in ('law_id', 'cell_id', 'actor'))
QUOTE = ASSIGNMENT['law']['text']
TEMPLATE = LAW + '@' + ACTOR


def write(name, value):
    OUT.mkdir(exist_ok=True)
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def observable(phrase, note, term, context):
    return {'template_id': TEMPLATE, 'phrase': phrase, 'note': note,
        'status': 'draft', 'observable_requirements': {
            'observables': [{'name': term, 'unit': 'structured',
                'description': 'Original 20 Hz body path, lane and indicator source.'}],
            'context_inputs': [{'name': context, 'unit': 'structured',
                'description': 'Original Native road, weather and area source for independent review.'}],
            'sweep_dimensions': [{'name': term, 'unit': 'category',
                'description': 'Controlled requested variant; no legal status inferred.'}],
            'landmarks': [],
            'recording_needs': [{'name': term, 'unit': 'structured',
                'description': 'Synchronized original body, signal, weather and four camera frames.'}],
            'limitations': ['Area class, visible pixels, intersample continuity and legal judgment remain unassessed.']}}


def main():
    relevance = {'actor': ACTOR, 'cell_id': CELL, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': QUOTE, 'applies_to': [ACTOR],
            'relevance_type': 'direct', 'confidence': 'high',
            'notes': 'Frozen same-direction multilane lane-change cell; original area source requires review.'}],
        'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance-batch', relevance),
        'relevance': write('relevance', relevance)}
    judgments = [
        ('during not less than the last 100 feet traveled in a business or residential district',
         'Original area class and complete sampled path distance must be established.',
         'continuous_signal_distance_before_course_change', 'area_class_source'),
        ('during not less than the last 300 feet traveled in any other area',
         'Original other-area class and complete sampled path distance must be established.',
         'continuous_signal_distance_before_course_change', 'area_class_source'),
        ('shall be given continuously',
         'Post-tick samples test sampled continuity; visible pixels and intersample behavior require review.',
         'sig.turn_indicator', 'original_video'),
        ('prior to changing the course of a vehicle',
         'Original body/lane transition must establish actual course change independent of command.',
         'drv.lane_change', 'lane_source'),
        ('regardless of the weather',
         'Original precipitation source is retained; no weather waiver or changed threshold is inferred.',
         'env.precipitation', 'weather_source')]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'quote': QUOTE, 'status': 'draft', 'structure': {
            'activation': {'description': 'Driver changes course from a direct course, including same-direction lane change',
                'source_clause': 'turn right or left, or otherwise turn a vehicle from a direct course'},
            'obligation': {'description': 'Give a continuous signal over the applicable final traveled distance before course change',
                'type': 'must', 'source_clause': 'shall be given continuously during not less than the last 100 feet traveled in a business or residential district and not less than the last 300 feet traveled in any other area prior to changing the course of a vehicle'},
            'exceptions': [],
            'timing': {'description': 'Final traveled path distance; weather does not alter the duty'},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                for phrase, note, _, _ in judgments]},
        'parameter_refs': [
            {'name': 'area_class_request', 'kind': 'world_setup',
             'range_or_domain': ['business_or_residential', 'other']},
            {'name': 'signal_distance_ft', 'kind': 'controller',
             'range_or_domain': [90, 100, 110, 290, 300, 310]},
            {'name': 'signal_continuity_request', 'kind': 'controller',
             'range_or_domain': ['continuous', 'interrupted']},
            {'name': 'weather_request', 'kind': 'world_setup',
             'range_or_domain': ['clear', 'rain']},
            {'name': 'signal_side_request', 'kind': 'controller',
             'range_or_domain': ['left', 'right']}]}
    refs['template'] = write('template', template)
    refs['judgment_observables'] = [write('judgment_observables_' + str(i),
        observable(*item)) for i, item in enumerate(judgments, 1)]
    binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [{'name': 'same_direction_multilane_change_lane_request',
            'source': 'frozen C245490 cell and authored two-lane OpenDRIVE request'}],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [{'name': row['name'], 'kind': row['kind'],
            'range_or_domain': row['range_or_domain'], 'used_by_laws': [LAW]}
            for row in template['parameter_refs']]}
    refs['bindings'] = write('bindings', binding)
    plan = json.loads((HERE / 'case-plan.json').read_text())
    constructions = {case['case_id']: json.loads((HERE / ('construction.json' if
        case['case_id'].endswith('__90') else 'native/selected-drafts/' +
        case['case_id'].rsplit('__', 1)[-1] + '/primary/construction.json')).read_text())
        for case in plan['cases']}
    entries = []
    for case in plan['cases']:
        cid = case['case_id']
        primary = {'interrupt': 'signal_continuity_request',
            'rain': 'weather_request',
            'right': 'signal_side_request'}.get(case.get('case_variant'),
                'signal_distance_ft')
        entries.append({'case_id': cid, 'target_law_id': LAW,
            'target_type': 'boundary_probe',
            'probe': {'primary_variable': primary,
                'comparison_or_standard': 'Original sampled final path distance and applicable area class; no inferred legal verdict',
                'target_value_or_branch': cid.rsplit('__', 1)[-1]},
            'paired_probe_id': 'C245490-signal-course-change-contrasts',
            'deliberate_differences': [primary],
            'rationale': 'Source-bound request contrast; original area and pixels remain unverified.',
            'recording_description': constructions[cid]['recording_description'],
            'unresolved_judgment_calls': [row[0] for row in judgments],
            'variable_assignments': {
                'area_class_request': {'kind': 'world_setup', 'unit': 'category',
                    'value': case['area_class_request']},
                'signal_distance_ft': {'kind': 'controller', 'unit': 'ft',
                    'value': case['requested_setting']},
                'signal_continuity_request': {'kind': 'controller', 'unit': 'category',
                    'value': 'interrupted' if case.get('case_variant') == 'interrupt' else 'continuous'},
                'weather_request': {'kind': 'world_setup', 'unit': 'category',
                    'value': 'rain' if case.get('case_variant') == 'rain' else 'clear'},
                'signal_side_request': {'kind': 'controller', 'unit': 'category',
                    'value': 'right' if case.get('case_variant') == 'right' else 'left'}}})
    baseline = {'case_id': HERE.name + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Unselected neutral signaling definition.',
        'recording_description': constructions[plan['cases'][0]['case_id']]['recording_description'],
        'unresolved_judgment_calls': [row[0] for row in judgments],
        'variable_assignments': entries[0]['variable_assignments']}
    for entry in entries:
        changes = [name for name, value in entry['variable_assignments'].items()
            if value != baseline['variable_assignments'][name]]
        entry['deliberate_differences'] = list(dict.fromkeys(
            entry['deliberate_differences'] + changes))
    sweep = {'sweep_id': 'signal_source_judgments', 'target_law_id': LAW,
        'judgment_refs': template['structure']['judgment_calls_needed'],
        'status': 'incomplete',
        'rationale': 'Twelve controlled requests do not establish original area class, visible signal pixels, intersample continuity or legal compliance.',
        'missing_inputs': ['Independent original area classification',
            'Original visible indicator and continuous signal review',
            'Original weather and lane-change source review']}
    cases = {'actor': ACTOR, 'cell_id': CELL, 'status': 'draft',
        'sweeps_expanded': True, 'cases': [baseline, *entries],
        'sweep_specs': [sweep]}
    refs['cases'] = write('cases', cases)
    index = {'assignment_id': HERE.name, 'format': 'worker-semantic-delivery',
        'stages': refs}
    write('semantic-index', index)
    return {'selected_cases': len(entries), 'judgments': len(judgments)}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
