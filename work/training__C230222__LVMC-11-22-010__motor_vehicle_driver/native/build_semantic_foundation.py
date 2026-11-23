"""Build and validate draft semantic stages for the exact attention duty."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SOURCE = REPO / 'inputs' / ROOT.name / 'assignment.json'
PROPOSALS = ROOT / 'proposals'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    assignment = json.loads(SOURCE.read_text())
    law = assignment['law']
    cell = assignment['cell']
    law_id = assignment['law_id']
    actor = assignment['actor']
    quote = law['text']
    assert quote == ('A person shall, when operating a vehicle, give his full '
                     'time and attention to the operation of the vehicle.')
    template_id = law_id + '@' + actor
    phrase = 'full time and attention to the operation of the vehicle'
    note = ('Vehicle kinematics and an unreviewed simulator camera do not establish '
            'a human driver\'s attention; direct original operator and scene evidence is required.')
    relevance = {
        'cell_id': cell['cell_id'], 'actor': actor, 'status': 'draft',
        'relevant_laws': [{
            'law_id': law_id, 'quote': quote, 'applies_to': [actor],
            'relevance_type': 'specific_match', 'confidence': 'medium',
            'notes': 'The grounded road/travel cell includes a motor vehicle driver; actual driver attention during operation needs original evidence.'}],
        'borderline_excluded': [],
    }
    template = {
        'template_id': template_id, 'law_id': law_id, 'actor': actor,
        'quote': quote, 'status': 'draft',
        'structure': {
            'law_id': law_id,
            'activation': {
                'condition': 'a person operating a vehicle', 'numeric_conditions': []},
            'obligation': {
                'type': 'must',
                'description': 'give full time and attention to vehicle operation',
                'source_clause': quote, 'numeric_conditions': []},
            'exceptions': [],
            'timing': {
                'description': 'throughout the observed vehicle-operation interval',
                'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note}],
        },
        'parameter_refs': [
            {'name': 'driver_attention_to_operation', 'kind': 'subject_behavior',
             'range_or_domain': 'unknown until independently reviewed original driver and scene evidence'},
            {'name': 'vehicle_operation_context', 'kind': 'world_setup',
             'range_or_domain': 'original Native vehicle, route and operator context, initially unknown'}],
    }
    judgment = {
        'template_id': template_id, 'phrase': phrase, 'note': note,
        'status': 'draft',
        'observable_requirements': {
            'observables': [
                {'name': 'ego_pose', 'unit': 'structured',
                 'description': 'Original frame-joined vehicle operation and path.'},
                {'name': 'ego_speed', 'unit': 'm/s',
                 'description': 'Original velocity magnitude for episode timing, not attention.'}],
            'context_inputs': [
                {'name': 'driver_attention_source_review', 'unit': 'structured',
                 'description': 'Original operator-facing evidence, visibility and independent review of the person while operating; unavailable from vehicle motion alone.'},
                {'name': 'native_driving_context', 'unit': 'structured',
                 'description': 'Original vehicle, route, camera pose, scene and time references.'}],
            'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [
                {'name': 'ego_pose', 'unit': 'structured',
                 'description': 'Frame-joined operation interval.'},
                {'name': 'driver_reference_video', 'unit': 'video',
                 'description': 'Original synchronized camera source; visual sufficiency requires review.'}],
            'limitations': [
                'A scripted CARLA vehicle has no demonstrated human driver attention state.',
                'Requested controls, kinematics and synthetic camera pixels cannot establish the legal duty.'],
        },
    }
    binding = {
        'cell_id': cell['cell_id'], 'actor': actor, 'status': 'draft',
        'established_contexts': [
            'The frozen road/travel cell and motor-vehicle-driver role are planning context; realized person, operation and attention remain source-review questions.'],
        'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [
            {'name': 'driver_attention_to_operation', 'kind': 'subject_behavior',
             'range_or_domain': 'original driver evidence, presently unobserved',
             'used_by_laws': [law_id]},
            {'name': 'vehicle_operation_context', 'kind': 'world_setup',
             'range_or_domain': 'realized original vehicle and route context',
             'used_by_laws': [law_id]}],
    }
    files = {
        'relevance_batch': ('relevance-batch.json', relevance),
        'relevance': ('relevance.json', relevance),
        'template': ('template.json', template),
        'judgment_observables': ('judgment-observables-1.json', judgment),
        'bindings': ('bindings.json', binding),
    }
    for filename, value in files.values():
        write(PROPOSALS / filename, value)
    from batch_pipeline import stages
    rules = json.loads((stages.ROOT / 'data/canonical_parameter_aliases.json').read_text())
    request = {'cell': cell, 'actor': actor}
    for stage in ('relevance_batch', 'relevance'):
        stages.validate(stage, deepcopy(relevance), {
            'request': request, 'law_records': {law_id: law}, 'dependencies': []})
    stages.validate('template', deepcopy(template), {
        'request': {'law_id': law_id, 'actor': actor}, 'law_record': law,
        'canonical_parameter_rules': rules, 'dependencies': []})
    stages.validate('judgment_observables', deepcopy(judgment), {
        'request': {'template_id': template_id, 'phrase': phrase, 'note': note},
        'dependencies': []})
    stages.validate('bindings', deepcopy(binding), {
        'request': dict(request, template_ids=[template_id]),
        'canonical_parameter_rules': rules, 'dependencies': [template]})
    index = {
        'format': 'worker-semantic-foundation-v1',
        'assignment_id': assignment['assignment_id'],
        'input_sha256': sha(SOURCE), 'status': 'partial_foundation',
        'stages': {stage: {'path': 'proposals/' + filename,
                           'sha256': sha(PROPOSALS / filename)}
                   for stage, (filename, _) in files.items()},
        'case_stage_present': False, 'delivery_selected': False,
        'original_driver_attention_observed': False,
    }
    write(PROPOSALS / 'semantic-foundation-index.json', index)
    print(json.dumps({'validated_stages': 5, 'index_sha256':
                      sha(PROPOSALS / 'semantic-foundation-index.json'),
                      'delivery_selected': False}))


if __name__ == '__main__':
    main()
