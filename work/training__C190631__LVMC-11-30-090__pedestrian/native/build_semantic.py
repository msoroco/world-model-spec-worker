"""Author source-bound semantic stages for the sidewalk and roadway pair."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
OUT = ROOT / 'proposals'
AID = ROOT.name
SOURCE = REPO / 'inputs' / AID / 'assignment.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name, 'sha256': sha(path)}


def main():
    assignment = json.loads(SOURCE.read_text())
    law, cell, actor = assignment['law'], assignment['cell'], assignment['actor']
    lid = law['id']
    tid = lid + '@' + actor
    exact = 'Where sidewalks are provided it shall be unlawful for any pedestrian to walk along and upon an adjacent roadway.'
    assert law['text'] == exact
    phrases = [
        ('Where sidewalks are provided', 'Verify actual sidewalk provision and pedestrian use from Native geometry and original views; a cell label is insufficient.'),
        ('walk along and upon an adjacent roadway', 'Use original pedestrian footprints and route heading, surveyed sidewalk and roadway, and source review of adjacency; no legal distance cutoff is supplied.'),
    ]
    relevance = {'cell_id': cell['cell_id'], 'actor': actor, 'status': 'draft',
        'relevant_laws': [{'law_id': lid, 'quote': exact, 'applies_to': [actor],
            'relevance_type': 'specific_match', 'confidence': 'low',
            'notes': 'The overpass and sidewalk cell is planning context; original sidewalk provision, pedestrian use and adjacent roadway walking need source proof.'}],
        'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance-batch.json', relevance),
            'relevance': write('relevance.json', relevance)}
    parameters = [
        {'name': 'sidewalk_provision_context', 'kind': 'world_setup', 'range_or_domain': 'original Native sidewalk provision and pedestrian-use purpose'},
        {'name': 'adjacent_roadway_context', 'kind': 'world_setup', 'range_or_domain': 'source-surveyed adjacent roadway and sidewalk polygons'},
        {'name': 'walking_surface', 'kind': 'controller', 'range_or_domain': ['sidewalk', 'roadway']},
    ]
    template = {'template_id': tid, 'law_id': lid, 'actor': actor, 'quote': exact, 'status': 'draft',
        'structure': {'law_id': lid,
            'activation': {'condition': 'sidewalks are provided', 'numeric_conditions': []},
            'obligation': {'type': 'must_not', 'description': 'pedestrian must not walk along and upon an adjacent roadway where sidewalks are provided', 'source_clause': exact, 'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'during observed pedestrian travel on the adjacent roadway', 'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': p, 'note': n} for p, n in phrases]},
        'parameter_refs': parameters}
    refs['template'] = write('template.json', template)
    requirements = [
        {'observables': [{'name': 'st.sidewalk', 'unit': 'source observation', 'description': 'Original Native sidewalk provision and use observations.'}],
         'context_inputs': [],
         'recording_needs': [{'name': 'st.sidewalk', 'unit': 'source observation', 'description': 'Source-surveyed sidewalk and synchronized camera views.'}],
         'limitations': ['A synthetic sidewalk strip does not prove an actual provided sidewalk or legal purpose.']},
        {'observables': [{'name': 'st.roadway', 'unit': 'source observation', 'description': 'Original adjacent roadway geometry and pedestrian occupancy.'},
                         {'name': 'kin.heading', 'unit': 'source observation', 'description': 'Original travel heading relative to surveyed road.'}],
         'context_inputs': [],
         'recording_needs': [{'name': 'st.roadway', 'unit': 'source observation', 'description': 'Source-surveyed roadway and original frame-joined footprints.'},
                             {'name': 'rel.occupies', 'unit': 'source observation', 'description': 'Full-frame pedestrian surface occupancy.'},
                             {'name': 'kin.heading', 'unit': 'source observation', 'description': 'Original path heading.'}],
         'limitations': ['Adjacency and walking along the road require original source review; no legal geometric cutoff is supplied.']},
    ]
    refs['judgment_observables'] = []
    for i, ((phrase, note), req) in enumerate(zip(phrases, requirements), 1):
        value = {'template_id': tid, 'phrase': phrase, 'note': note, 'status': 'draft',
                 'observable_requirements': dict(req, sweep_dimensions=[], landmarks=[])}
        refs['judgment_observables'].append(write(f'judgment-observables-{i}.json', value))
    binding = {'cell_id': cell['cell_id'], 'actor': actor, 'status': 'draft',
        'established_contexts': ['Overpass layout is planning context; sidewalk provision and adjacency need original Native review.'],
        'law_refs': [{'template_id': tid, 'binding_kind': 'direct'}], 'context_refs': [],
        'fixed_parameters': [],
        'variable_parameters': [dict(p, used_by_laws=[lid]) for p in parameters]}
    refs['bindings'] = write('bindings.json', binding)
    cases = json.loads((OUT / 'cases.json').read_text())
    common = {'sidewalk_provision_context': {'kind': 'world_setup', 'value': 'source-reviewed provided pedestrian sidewalk required'},
              'adjacent_roadway_context': {'kind': 'world_setup', 'value': 'surveyed upper roadway next to sidewalk'}}
    for case in cases['cases']:
        suffix = case['case_id'].rsplit('__', 1)[-1]
        case['variable_assignments'] = dict(common, walking_surface=case['variable_assignments']['walking_surface'])
        case['unresolved_judgment_calls'] = [p for p, _ in phrases]
        source = ROOT / 'draft-roadway' / suffix / 'primary' / 'construction.json' if suffix != 'baseline' else ROOT / 'draft-roadway/probe_01/primary/construction.json'
        case['recording_description'] = json.loads(source.read_text())['recording_description']
        if suffix != 'baseline':
            case['target_type'] = 'judgment_sweep'
            case['paired_probe_id'] = 'c190631-walking-surface-pair'
            case['deliberate_differences'] = ['walking_surface']
            case['probe'] = {'primary_variable': 'walking_surface',
                             'comparison_or_standard': 'original measured sidewalk versus adjacent roadway travel',
                             'target_value_or_branch': suffix}
    cases['sweep_specs'] = [{'sweep_id': 'sidewalk_provision_and_adjacency', 'target_law_id': lid,
        'judgment_refs': template['structure']['judgment_calls_needed'], 'status': 'incomplete',
        'rationale': 'Qualitative sidewalk provision and adjacency need original Native survey, pixels and source review before a judgment sweep can be finalized.',
        'missing_inputs': ['Original Native sidewalk provision and pedestrian-use evidence', 'Original adjacency and roadway-walking source observations']}]
    cases['sweeps_expanded'] = True
    refs['cases'] = write('cases.json', cases)
    write('semantic-index.json', {'format': 'worker-semantic-delivery', 'assignment_id': AID, 'stages': refs})
    from batch_pipeline import stages
    rules = json.loads((stages.ROOT / 'data/canonical_parameter_aliases.json').read_text())
    request = {'cell': cell, 'actor': actor}
    for stage in ('relevance_batch', 'relevance'):
        stages.validate(stage, deepcopy(relevance), {'request': request, 'law_records': {lid: law}, 'dependencies': []})
    stages.validate('template', deepcopy(template), {'request': {'law_id': lid, 'actor': actor}, 'law_record': law, 'canonical_parameter_rules': rules, 'dependencies': []})
    completed = deepcopy(template)
    for (phrase, note), req in zip(phrases, requirements):
        obs = {'template_id': tid, 'phrase': phrase, 'note': note, 'status': 'draft', 'observable_requirements': dict(req, sweep_dimensions=[], landmarks=[])}
        stages.validate('judgment_observables', deepcopy(obs), {'request': {'template_id': tid, 'phrase': phrase, 'note': note}, 'dependencies': []})
        next(j for j in completed['structure']['judgment_calls_needed'] if j['phrase'] == phrase)['observable_requirements'] = obs['observable_requirements']
    stages.validate('bindings', deepcopy(binding), {'request': dict(request, template_ids=[tid]), 'canonical_parameter_rules': rules, 'dependencies': [template]})
    stages.validate('cases', deepcopy(cases), {'request': request, 'dependencies': [binding], 'templates': [completed], 'canonical_parameter_rules': rules, 'judgment_completion_policy': {}})
    print('semantic stages pass')


if __name__ == '__main__':
    main()
