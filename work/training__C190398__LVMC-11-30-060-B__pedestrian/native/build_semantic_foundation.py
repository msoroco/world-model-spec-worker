"""Build source-bound draft semantic stages for LVMC 11.30.060(B)."""
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


def write(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return path


def main():
    assignment = json.loads(SOURCE.read_text())
    law = assignment['law']
    text = law['text']
    lid = law['id']
    actor = assignment['actor']
    cell = assignment['cell']
    tid = lid + '@' + actor
    duty = 'Any pedestrian crossing a roadway at a point where a pedestrian tunnel or overhead pedestrian crossing has been provided shall yield the right-of-way to all vehicles upon the roadway.'
    exception = 'The foregoing rules in this Section shall have no application under the conditions stated in Section 11.30.070 when pedestrians are prohibited from crossing at certain designated places.'
    assert text == duty + ' ' + exception
    phrases = [
        ('at a point where a pedestrian tunnel or overhead pedestrian crossing has been provided',
         'Record both the roadway crossing point and the actual grade separation footprint; the law supplies no distance cutoff.'),
        ('yield the right-of-way to all vehicles upon the roadway',
         'Inventory all roadway vehicles over the full crossing interval; braking alone cannot decide a right-of-way judgment.'),
        ('conditions stated in Section 11.30.070 when pedestrians are prohibited from crossing at certain designated places',
         'Review the applicable prohibition and district or designated-place facts from original municipal and scene sources.'),
    ]
    relevance = {
        'cell_id': cell['cell_id'], 'actor': actor, 'status': 'draft',
        'relevant_laws': [{'law_id': lid, 'quote': duty, 'applies_to': [actor],
            'relevance_type': 'specific_match', 'confidence': 'low',
            'notes': 'The frozen cell names an overpass and straight pedestrian motion, but roadway crossing and grade separation placement need original evidence.'}],
        'borderline_excluded': [],
    }
    template = {
        'template_id': tid, 'law_id': lid, 'actor': actor, 'quote': text, 'status': 'draft',
        'structure': {
            'law_id': lid,
            'activation': {'condition': 'pedestrian crosses roadway at a point with a provided tunnel or overhead pedestrian crossing', 'numeric_conditions': []},
            'obligation': {'type': 'must', 'description': 'pedestrian yields right-of-way to all vehicles upon roadway', 'source_clause': duty, 'numeric_conditions': []},
            'exceptions': [{'trigger': 'conditions stated in Section 11.30.070 when pedestrians are prohibited from crossing at certain designated places',
                'effect': 'this Section does not apply under those conditions', 'replacement_obligation': 'requires separate review of Section 11.30.070', 'source_clause': exception}],
            'timing': {'description': 'during the observed roadway crossing and interactions with every vehicle upon it', 'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note in phrases],
        },
        'parameter_refs': [
            {'name': 'grade_separation_crossing_context', 'kind': 'world_setup', 'range_or_domain': 'source-verified roadway, overpass or tunnel footprint and crossing point'},
            {'name': 'roadway_vehicle_context', 'kind': 'world_setup', 'range_or_domain': 'all vehicles upon the roadway during the crossing'},
            {'name': 'pedestrian_yield_behavior', 'kind': 'subject_behavior', 'range_or_domain': 'original crossing and interactions, never preassigned'},
            {'name': 'section_070_prohibition_context', 'kind': 'world_setup', 'range_or_domain': 'municipal prohibition conditions and original designated-place facts'},
        ],
    }
    observables = [
        {
            'observables': [{'name': 'pedestrian_roadway_occupancy', 'unit': 'boolean time series', 'description': 'Source-derived pedestrian footprint intersecting roadway polygon over full crossing.'},
                            {'name': 'crossing_point', 'unit': 'world coordinates', 'description': 'Source-derived entry and exit points, with uncertainty.'}],
            'context_inputs': [{'name': 'roadway_polygon', 'unit': 'world geometry', 'description': 'Original road boundaries, excluding shoulder.'},
                               {'name': 'grade_separation_footprint', 'unit': 'world geometry', 'description': 'Verified provided overpass or tunnel footprint and access.'}],
            'recording_needs': [{'name': 'pedestrian_pose', 'unit': 'world coordinates', 'description': 'Original synchronized pedestrian trajectory.'},
                                {'name': 'scene_cameras', 'unit': 'video', 'description': 'Four synchronized source-camera views of road and structure.'}],
            'limitations': ['The cell label alone does not prove the pedestrian crosses the roadway.', 'No legal spatial cutoff is supplied.'],
        },
        {
            'observables': [{'name': 'pedestrian_roadway_occupancy', 'unit': 'boolean time series', 'description': 'Full crossing interval.'},
                            {'name': 'vehicle_pedestrian_interaction', 'unit': 'structured time series', 'description': 'Ordered approach, overlap, delay and passage for each vehicle.'}],
            'context_inputs': [{'name': 'roadway_vehicle_inventory', 'unit': 'structured', 'description': 'All roadway vehicles with classes, paths and frame-joined identity.'},
                               {'name': 'priority_context', 'unit': 'structured', 'description': 'Signs, controls and applicable context for independent judgment.'}],
            'recording_needs': [{'name': 'pedestrian_and_vehicle_poses', 'unit': 'world coordinates', 'description': 'Original synchronized trajectories and footprints.'},
                                {'name': 'source_camera_views', 'unit': 'video', 'description': 'Full four-camera source capture.'}],
            'limitations': ['Vehicle hard braking is diagnostic context, not proof of pedestrian failure to yield.', 'A requested yield setting is not a measured result.'],
        },
        {
            'observables': [{'name': 'crossing_point', 'unit': 'world coordinates', 'description': 'Original crossing location for designated-place review.'}],
            'context_inputs': [{'name': 'section_070_authority', 'unit': 'source citation', 'description': 'Exact applicable prohibition text and designation authority.'},
                               {'name': 'district_and_place', 'unit': 'structured', 'description': 'Source-grounded district and crossing designation.'}],
            'recording_needs': [{'name': 'crossing_route_and_signs', 'unit': 'world geometry and video', 'description': 'Route, boundaries, markings and visible controls.'}],
            'limitations': ['The assignment supplies a reference to Section 11.30.070 but does not establish all applicability facts.', 'Do not treat the prohibition exception as absent by default.'],
        },
    ]
    files = {'relevance_batch': ('relevance-batch.json', relevance),
             'relevance': ('relevance.json', relevance),
             'template': ('template.json', template),
             'bindings': ('bindings.json', {
                 'cell_id': cell['cell_id'], 'actor': actor, 'status': 'draft',
                 'established_contexts': ['The overpass cell and pedestrian actor are planning context; roadway crossing, structure placement and vehicle interactions remain unverified.'],
                 'law_refs': [{'template_id': tid, 'binding_kind': 'direct'}],
                 'context_refs': [], 'fixed_parameters': [],
                 'variable_parameters': [dict(p, used_by_laws=[lid]) for p in template['parameter_refs']],
             })}
    for i, ((phrase, note), needs) in enumerate(zip(phrases, observables), 1):
        files['judgment_observables_' + str(i)] = ('judgment-observables-' + str(i) + '.json', {
            'template_id': tid, 'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': dict(needs, sweep_dimensions=[], landmarks=[]),
        })
    for name, value in files.values():
        write(name, value)
    from batch_pipeline import stages
    rules = json.loads((stages.ROOT / 'data/canonical_parameter_aliases.json').read_text())
    req = {'cell': cell, 'actor': actor}
    for stage in ('relevance_batch', 'relevance'):
        stages.validate(stage, deepcopy(relevance), {'request': req, 'law_records': {lid: law}, 'dependencies': []})
    stages.validate('template', deepcopy(template), {'request': {'law_id': lid, 'actor': actor}, 'law_record': law, 'canonical_parameter_rules': rules, 'dependencies': []})
    for key in ('judgment_observables_1', 'judgment_observables_2', 'judgment_observables_3'):
        j = files[key][1]
        stages.validate('judgment_observables', deepcopy(j), {'request': {'template_id': tid, 'phrase': j['phrase'], 'note': j['note']}, 'dependencies': []})
    stages.validate('bindings', deepcopy(files['bindings'][1]), {'request': dict(req, template_ids=[tid]), 'canonical_parameter_rules': rules, 'dependencies': [template]})
    index = {'format': 'worker-semantic-foundation-v1', 'assignment_id': assignment['assignment_id'],
             'input_sha256': sha(SOURCE), 'status': 'partial_foundation',
             'stages': {key: {'path': 'proposals/' + name, 'sha256': sha(OUT / name)} for key, (name, _) in files.items()},
             'validated_stage_instances': 7, 'case_stage_present': False, 'delivery_selected': False}
    write('semantic-foundation-index.json', index)
    print(json.dumps({'validated_stage_instances': 7, 'index_sha256': sha(OUT / 'semantic-foundation-index.json')}))


if __name__ == '__main__':
    main()
