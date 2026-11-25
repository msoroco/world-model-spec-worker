"""Build source-honest draft semantic stages for the exact pedestrian cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
    law = assignment['law']
    law_id, actor, cell = plan['law_id'], plan['actor'], plan['cell_id']
    template_id = law_id + '@' + actor
    phrase = 'unless directed otherwise by another device as provided in NRS 484B.283'
    note = ('Device route applicability and source-governed entry or continuation '
            'cannot be decided from a synthetic indication label.')
    relevance = {'cell_id': cell, 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law_id, 'quote': law['text'],
                                    'applies_to': [actor],
                                    'relevance_type': 'direct circular-green pedestrian crosswalk branch',
                                    'confidence': 'high',
                                    'notes': 'Frozen witness selects the straight pedestrian crosswalk route.'}],
                 'borderline_excluded': []}
    write(ROOT / 'proposals/relevance.json', relevance)
    write(ROOT / 'proposals/relevance_batch.json', relevance)
    parameters = [
        ('circular_green_alone', 'world_setup', 'official facing signal shows circular green alone'),
        ('crosswalk_kind', 'world_setup', 'marked or source-qualified unmarked'),
        ('other_device_indication', 'world_setup', 'none, WALK or DONT_WALK'),
        ('device_modes', 'world_setup', 'absent, walk, flashing countdown, flashing without countdown, steady by frame'),
        ('pedestrian_enters_highway', 'controller', 'requested crossing or wait; actual entry remains measured'),
        ('entry_inside_crosswalk', 'world_setup', 'requested within or outside sourced crosswalk geometry'),
    ]
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
                'quote': law['text'],
                'structure': {'law_id': law_id,
                              'activation': {'condition': 'Pedestrian faces an official circular-green-alone signal at a public highway.',
                                             'numeric_conditions': []},
                              'obligation': {'description': 'Pedestrian may proceed within a marked or qualifying unmarked crosswalk, subject to another applicable device under NRS 484B.283.',
                                             'type': 'may', 'numeric_conditions': []},
                              'exceptions': [{'source_clause': phrase,
                                              'description': phrase, 'numeric_conditions': []}],
                              'timing': {'description': 'Original signal, device mode, entry and clearance are joined by frame.',
                                         'numeric_conditions': []},
                              'judgment_calls_needed': [{'phrase': phrase, 'note': note}]},
                'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain}
                                   for name, kind, domain in parameters]}
    write(ROOT / 'proposals/template.json', template)
    delivery_draft = ROOT / 'cases/marked_cross/delivery-construction.draft.json'
    record = json.loads(delivery_draft.read_text() if delivery_draft.is_file() else
                        (ROOT / 'cases/marked_cross/construction.json').read_text())['recording_description']
    observable = {'template_id': template_id, 'phrase': phrase, 'note': note,
                  'status': 'draft',
                  'observable_requirements': {
                      'observables': [{'name': 'pedestrian_body_center_xy_m', 'unit': 'structured',
                                       'description': 'Original pedestrian body center by frame.'}],
                      'context_inputs': [{'name': 'source_provenance', 'unit': 'metadata',
                                          'description': 'Source identities for map, official head and device inventory.'}],
                      'sweep_dimensions': [{'name': 'device_modes', 'unit': 'categorical',
                                            'description': 'Source-observed device mode categories; no legal threshold.'}],
                      'landmarks': [],
                      'recording_needs': [{'name': 'pedestrian_body_center_xy_m', 'unit': 'structured',
                                           'description': 'Timestamped original body positions.'}],
                      'limitations': ['Reviewed device applicability and route direction are absent from frozen evidence.']}}
    write(ROOT / 'proposals/judgment-1.json', observable)
    binding = {'cell_id': cell, 'actor': actor, 'status': 'draft',
               'established_contexts': ['public highway intersection', 'straight pedestrian route',
                                        'source-qualified crosswalk and official facing head pending review'],
               'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': name, 'kind': kind,
                                        'range_or_domain': domain,
                                        'used_by_laws': [law_id]}
                                       for name, kind, domain in parameters]}
    write(ROOT / 'proposals/bindings.json', binding)
    names = {name: kind for name, kind, _ in parameters}
    def values(raw):
        source = dict(raw)
        source.setdefault('device_modes', ['steady'] * 3 if source['other_device_indication'] == 'DONT_WALK'
                          else ['absent'] * 3)
        return {key: {'kind': names[key], 'value': source[key]} for key in names}
    baseline = {'case_id': ROOT.name + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Reference circular-green marked crosswalk and no contrary device.',
                'variable_assignments': values(plan['cases'][0]['scenario_parameters']),
                'recording_description': record, 'unresolved_judgment_calls': [phrase]}
    cases = [baseline]
    for case in plan['cases']:
        values_map = values(case['scenario_parameters'])
        changed = [key for key in names if values_map[key] != baseline['variable_assignments'][key]]
        primary = changed[0] if changed else 'crosswalk_kind'
        cases.append({'case_id': case['case_id'], 'target_law_id': law_id,
                      'target_type': 'boundary_probe', 'rationale': case['purpose'],
                      'variable_assignments': values_map,
                      'paired_probe_id': 'reference_vs_' + case['case_id'].split('__')[-1],
                      'deliberate_differences': changed,
                      'probe': {'primary_variable': primary,
                                'comparison_or_standard': 'source-measured reference case',
                                'target_value_or_branch': case['purpose']},
                      'recording_description': record,
                      'unresolved_judgment_calls': [phrase]})
    proposal = {'cell_id': cell, 'actor': actor, 'status': 'draft', 'cases': cases,
                'sweep_specs': [{'sweep_id': 'device_applicability_source_review',
                                 'target_law_id': law_id,
                                 'judgment_refs': [{'phrase': phrase, 'note': note}],
                                 'status': 'incomplete',
                                 'rationale': 'No reviewed Native device inventory or crosswalk route supports a source-bound applicability sweep.',
                                 'missing_inputs': ['reviewed Native intersection and official signal head',
                                                    'source-verified device route applicability and phase timing',
                                                    'physical pedestrian clearance feasibility']}],
                'diagnostic_only': False}
    write(ROOT / 'proposals/cases.json', proposal)
    refs = {'relevance_batch': 'proposals/relevance_batch.json',
            'relevance': 'proposals/relevance.json', 'template': 'proposals/template.json',
            'judgment_observables': ['proposals/judgment-1.json'],
            'bindings': 'proposals/bindings.json', 'cases': 'proposals/cases.json'}
    stages = {key: ([{'path': path, 'sha256': sha(ROOT / path)} for path in value]
                    if isinstance(value, list) else {'path': value, 'sha256': sha(ROOT / value)})
              for key, value in refs.items()}
    write(ROOT / 'proposals/semantic-index.json', {'format': 'worker-semantic-delivery',
                                                   'assignment_id': ROOT.name, 'stages': stages})
    return len(cases)


if __name__ == '__main__':
    print(build())
