"""Author source-quoted C10014 semantic stages while blocking remains a judgment."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'runtime/pipeline/scenario_pipeline'))
from batch_pipeline import stages


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = HERE/'proposals'/(name+'.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n')
    return {'path': path.relative_to(HERE).as_posix(), 'sha256': sha(path)}


def build():
    source = ROOT/'inputs'/HERE.name/'assignment.json'
    assignment = json.loads(source.read_text())
    law = assignment['law_record']
    law_id, cell_id, actor = (assignment[k] for k in ('law_id', 'cell_id', 'actor'))
    request = {'cell': assignment['cell'], 'actor': actor}
    common = {'request': request, 'law_records': {law_id: law}, 'dependencies': []}
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
        'relevant_laws': [{'law_id': law_id, 'quote': law['text'], 'applies_to': [actor],
            'relevance_type': 'specific_match', 'confidence': 'medium',
            'notes': 'The cell proposes an alley stop near a driveway entrance; actual alley and abutting-property access need original evidence.'}],
        'borderline_excluded': []}
    stages.validate('relevance_batch', relevance, common)
    stages.validate('relevance', relevance, common)
    refs = {'relevance_batch': write('relevance_batch', relevance),
            'relevance': write('relevance', relevance)}
    phrase = 'block the driveway or entrance to any abutting property'
    note = 'Qualitative access obstruction; overlap alone does not decide legal blocking.'
    template_id = law_id+'@'+actor
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
        'status': 'draft', 'quote': law['text'],
        'structure': {
            'activation': {'context': 'within an alley beside an entrance to abutting property',
                           'subject': 'person stopping, standing or parking a vehicle'},
            'obligation': {'type': 'must_not',
                           'action': 'stop, stand or park in a position that blocks the driveway or entrance',
                           'source_clause': 'shall not stop, stand or park a vehicle within an alley in such position as to block the driveway or entrance to any abutting property'},
            'exceptions': [],
            'timing': {'description': 'during the stopped or standing interval at the entrance',
                       'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note}]},
        'parameter_refs': [
            {'name': 'alley_geometry', 'kind': 'world_setup',
             'range_or_domain': 'source-verified alley road and lane, with entrance corridor'},
            {'name': 'abutting_property_access', 'kind': 'world_setup',
             'range_or_domain': 'source-verified driveway or entrance and actual property access'},
            {'name': 'ego_trajectory', 'kind': 'subject_behavior',
             'range_or_domain': 'retained original frame-joined pose, body and motion'},
            {'name': 'commanded_stop_station_m', 'kind': 'controller',
             'range_or_domain': 'predeclared reference or entrance stop station'},
            {'name': 'commanded_approach_speed_mps', 'kind': 'controller',
             'range_or_domain': 'predeclared approach speed, distinct from observed ego speed'},
            {'name': 'camera_policy', 'kind': 'controller',
             'range_or_domain': 'predeclared four-camera framing or wider fallback'}]}
    rules = json.loads((stages.ROOT/'data/canonical_parameter_aliases.json').read_text())
    stages.validate('template', template, {'request': {'law_id': law_id, 'actor': actor},
        'law_record': law, 'canonical_parameter_rules': rules, 'dependencies': []})
    refs['template'] = write('template', template)
    observables = {'template_id': template_id, 'phrase': phrase, 'note': note,
        'status': 'draft', 'observable_requirements': {
            'observables': [
                {'name': 'st.alley', 'unit': 'structured',
                 'description': 'Original road and lane identity throughout the stop interval.'},
                {'name': 'rel.occupies', 'unit': 'structured',
                 'description': 'Original full vehicle footprint and lane relation.'},
                {'name': 'ego_speed', 'unit': 'structured',
                 'description': 'Measured original velocity and stationary interval.'}],
            'context_inputs': [
                {'name': 'surveyed_alley_entrance', 'unit': 'structured',
                 'description': 'Source-hashed Native lane survey, entrance boundary and property-access review context.'}],
            'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [
                {'name': 'st.driveway_or_alley_entrance', 'unit': 'structured',
                 'description': 'Source-backed entrance and abutting-property access designation.'},
                {'name': 'kin.position', 'unit': 'structured',
                 'description': 'Frame-joined original actor center and heading.'},
                {'name': 'kin.extent', 'unit': 'structured',
                 'description': 'Frame-joined original full body footprint.'}],
            'limitations': [
                'The statute supplies no numeric overlap threshold for blocking.',
                'Authored alley geometry and synthetic pixels do not establish actual access or legal obstruction.']}}
    stages.validate('judgment_observables', observables,
        {'request': {'template_id': template_id, 'phrase': phrase, 'note': note},
         'dependencies': []})
    refs['judgment_observables'] = [write('judgment_observables_blocking', observables)]
    variables = [
        ('alley_geometry', 'world_setup', 'source-verified Native alley and entrance geometry'),
        ('abutting_property_access', 'world_setup', 'source-verified actual driveway/access context'),
        ('ego_trajectory', 'subject_behavior', 'observed original body, pose and speed history'),
        ('commanded_stop_station_m', 'controller', 'reference or entrance stop station in m'),
        ('commanded_approach_speed_mps', 'controller', 'predeclared approach speed in m/s'),
        ('camera_policy', 'controller', 'four-view nominal or wider fallback')]
    binding = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
        'established_contexts': [{'name': 'alley_stop_near_driveway',
                                  'source': 'frozen catalog cell; physical access unverified'}],
        'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [{'name': name, 'kind': kind,
            'range_or_domain': domain, 'used_by_laws': [law_id]}
            for name, kind, domain in variables]}
    stages.validate('bindings', binding, {'request': dict(request, template_ids=[template_id]),
        'canonical_parameter_rules': rules, 'dependencies': [template]})
    refs['bindings'] = write('bindings', binding)
    proof = {'format': 'c10014-semantic-foundation-v1',
             'assignment_id': HERE.name, 'assignment_sha256': sha(source),
             'references': refs,
             'stages_validated': ['relevance_batch', 'relevance', 'template',
                                  'judgment_observables', 'bindings'],
             'cases_stage_validated': False, 'original_native_observed': False,
             'legal_verdict': None}
    write('semantic-foundation-proof', proof)
    return {'validated_stages': 5,
            'proof_sha256': sha(HERE/'proposals/semantic-foundation-proof.json')}


if __name__ == '__main__':
    print(json.dumps(build()))
