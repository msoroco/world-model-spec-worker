"""Draft source-grounded semantic stages for flashing-yellow arrow duty."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SOURCE = REPO / 'inputs' / ROOT.name / 'assignment.json'
OUT = ROOT / 'proposals'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    assignment = json.loads(SOURCE.read_text())
    law = assignment['law']
    quote = law['text']
    law_id = assignment['law_id']
    actor = assignment['actor']
    template_id = law_id + '@' + actor
    calls = [
        ('facing the signal', 'Original signal placement, orientation, visible indication and ego approach require independent review.'),
        ('cautiously enter the intersection', 'Motion measurements cannot decide cautiousness; original source and independent judgment remain necessary.'),
        ('movement indicated by the arrow signal, or other such movement as is permitted by other signal indications displayed at the same time', 'Original arrow and concurrent indication pixels and governance must be reviewed separately.'),
        ('pedestrians lawfully within the intersection or an adjacent crosswalk', 'Pedestrian location and lawful status require original participant and signal context.'),
        ('other traffic lawfully within the intersection', 'Other-vehicle location and lawful status require original participant and signal context.'),
    ]
    relevance = {'cell_id': assignment['cell_id'], 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law_id, 'quote': quote, 'applies_to': [actor],
                                    'relevance_type': 'specific_match', 'confidence': 'medium',
                                    'notes': 'Frozen intersection/turn/other-vehicle cell supports a motor-vehicle driver flashing-arrow turn request; actual governance and legal facts remain source review.'}],
                 'borderline_excluded': []}
    variables = [
        ('signal_governance', 'world_setup', 'original signal placement, pixels and approach, unknown before capture'),
        ('concurrent_indication', 'world_setup', 'original simultaneous indication, unknown before capture'),
        ('ego_turn_path', 'controller', 'requested right or left turn path; physical source measurement separate'),
        ('ego_release_frame', 'controller', 'engineering release request, not a legal cutoff'),
        ('pedestrian_lawful_status', 'subject_behavior', 'unknown until independent original-source review'),
        ('other_traffic_lawful_status', 'subject_behavior', 'unknown until independent original-source review'),
        ('cautious_entry_status', 'subject_behavior', 'unknown until independent original-source review'),
    ]
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
                'quote': quote, 'status': 'draft',
                'structure': {'law_id': law_id,
                              'activation': {'condition': 'vehicular traffic facing a flashing yellow turn arrow, alone or with another signal', 'numeric_conditions': []},
                              'obligation': {'type': 'must',
                                             'description': 'cautiously enter only for an indicated or concurrently permitted movement and yield to lawful pedestrians and other traffic within the named areas',
                                             'source_clause': quote, 'numeric_conditions': []},
                              'exceptions': [],
                              'timing': {'description': 'during the flashing-yellow arrow approach and entry', 'numeric_conditions': []},
                              'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note in calls]},
                'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain}
                                   for name, kind, domain in variables]}
    bindings = {'cell_id': assignment['cell_id'], 'actor': actor, 'status': 'draft',
                'established_contexts': ['Frozen intersection and motor-vehicle turn are planning context; actual signal and participant facts require original sources.'],
                'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
                'context_refs': [], 'fixed_parameters': [],
                'variable_parameters': [{'name': name, 'kind': kind, 'range_or_domain': domain,
                                         'used_by_laws': ([law_id] if kind != 'controller' else [])}
                                        for name, kind, domain in variables]}
    judgments = []
    for index, (phrase, note) in enumerate(calls, 1):
        judgment = {'template_id': template_id, 'phrase': phrase, 'note': note,
                    'status': 'draft',
                    'observable_requirements': {
                        'observables': [
                            {'name': 'ego_motion', 'unit': 'structured', 'description': 'Original frame-joined position and path.'},
                            {'name': 'signal_pixels', 'unit': 'video', 'description': 'Original synchronized signal and concurrent indication view.'},
                            {'name': 'participant_motion', 'unit': 'structured', 'description': 'Original frame-joined pedestrian or other-vehicle position where applicable.'}],
                        'context_inputs': [
                            {'name': 'source_law_and_signal_governance', 'unit': 'structured', 'description': 'Original signal orientation, controlling lane and exact statutory source.'},
                            {'name': 'lawful_status_review', 'unit': 'structured', 'description': 'Independent participant and signal review; unavailable from scripted intent.'}],
                        'sweep_dimensions': [], 'landmarks': [],
                        'recording_needs': [
                            {'name': 'turn_history', 'unit': 'structured', 'description': 'Original frame-joined ego, signal and participant history.'},
                            {'name': 'four_camera_video', 'unit': 'video', 'description': 'Original synchronized four-camera capture.'}],
                        'limitations': ['A controller request and synthetic fixture cannot establish legal compliance.',
                                        'Lawful status, signal governance and cautiousness need independent original-source review.']}}
        path = OUT / f'judgment-observables-{index}.json'
        dump(path, judgment)
        judgments.append((path, judgment))
    for path, value in ((OUT / 'relevance-batch.json', relevance),
                        (OUT / 'relevance.json', relevance),
                        (OUT / 'template.json', template),
                        (OUT / 'bindings.json', bindings)):
        dump(path, value)
    from batch_pipeline import stages
    rules = json.loads((stages.ROOT / 'data/canonical_parameter_aliases.json').read_text())
    request = {'cell': assignment['cell'], 'actor': actor}
    for stage in ('relevance_batch', 'relevance'):
        stages.validate(stage, deepcopy(relevance), {'request': request,
                        'law_records': {law_id: law}, 'dependencies': []})
    stages.validate('template', deepcopy(template), {'request': {'law_id': law_id, 'actor': actor},
                    'law_record': law, 'canonical_parameter_rules': rules, 'dependencies': []})
    for path, judgment in judgments:
        stages.validate('judgment_observables', deepcopy(judgment),
                        {'request': {'template_id': template_id, 'phrase': judgment['phrase'],
                                     'note': judgment['note']}, 'dependencies': []})
    stages.validate('bindings', deepcopy(bindings), {'request': dict(request,
                    template_ids=[template_id]), 'canonical_parameter_rules': rules,
                    'dependencies': [template]})
    index = {'format': 'worker-semantic-delivery', 'assignment_id': ROOT.name,
             'status': 'draft', 'original_native_observed': False,
             'stages': {name: {'path': 'proposals/' + filename,
                               'sha256': sha(OUT / filename)}
                        for name, filename in (('relevance_batch', 'relevance-batch.json'),
                                               ('relevance', 'relevance.json'),
                                               ('template', 'template.json'),
                                               ('bindings', 'bindings.json'))}}
    index['stages']['judgment_observables'] = [
        {'path': str(path.relative_to(ROOT)), 'sha256': sha(path)} for path, _ in judgments]
    dump(OUT / 'semantic-index.json', index)
    print(json.dumps({'validated_stages': 9, 'index_sha256': sha(OUT / 'semantic-index.json')}))


if __name__ == '__main__':
    main()
