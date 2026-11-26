"""Author source-faithful canonical stage proposals for graded standing."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
OUT = FOLDER / 'proposals'
ASSIGNMENT = FOLDER.name
LAW = 'NRS-484B-533'
ACTOR = 'motor_vehicle_driver'
TEXT = ('A vehicle shall not be permitted to stand unattended upon any perceptible grade '
        'without stopping the engine and effectively setting the brake thereon and '
        'turning the front wheels to the curb or side of the highway.')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, obj):
    path = OUT / name
    path.write_text(json.dumps(obj, indent=2) + '\n')
    return {'path': 'proposals/' + name, 'sha256': sha(path)}


def build():
    relevance = {'cell_id': 'C276263', 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
            'relevance_type': 'specific_match', 'confidence': 'high',
            'notes': 'The catalog cell is a motor-vehicle stand on an authored grade; original highway, grade, attendance and duty observations require review.'}],
        'borderline_excluded': []}
    batch = write('relevance_batch.json', relevance)
    rel = write('relevance.json', relevance)
    parameters = [
        {'name': 'engine_operation', 'kind': 'subject_behavior', 'range_or_domain': 'original same-frame boolean operation sensor'},
        {'name': 'parking_brake', 'kind': 'controller', 'range_or_domain': 'original same-frame parking-brake readback and effective holding review'},
        {'name': 'front_wheel_orientation', 'kind': 'subject_behavior', 'range_or_domain': 'calibrated original wheel orientation relative to surveyed curb'}]
    judgments = [
        {'phrase': 'unattended', 'note': 'Original cabin occupancy and identified responsible-person absence require review.'},
        {'phrase': 'perceptible grade', 'note': 'The authored 4 percent grade is an engineering request; perceptibility is a judgment, not a numeric legal cutoff.'},
        {'phrase': 'effectively setting the brake', 'note': 'Original brake command/readback and absence of movement require physical review.'},
        {'phrase': 'turning the front wheels to the curb or side of the highway', 'note': 'Original calibrated wheel orientation and right-curb survey require review.'}]
    template = {'template_id': LAW + '@' + ACTOR, 'law_id': LAW,
        'actor': ACTOR, 'status': 'draft', 'quote': TEXT,
        'structure': {'law_id': LAW,
            'activation': {'condition': 'A motor vehicle stands unattended upon a perceptible highway grade', 'numeric_conditions': []},
            'obligation': {'type': 'must_not', 'description': 'Permit unattended graded standing without stopping the engine, effectively setting the brake, and turning front wheels toward the curb or highway side',
                'source_clause': 'shall not be permitted to stand unattended upon any perceptible grade without stopping the engine and effectively setting the brake thereon and turning the front wheels to the curb or side of the highway',
                'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'Engine and brake are checked over the unattended stand; wheel direction is required before departure and throughout that stand', 'numeric_conditions': []},
            'judgment_calls_needed': judgments}, 'parameter_refs': parameters}
    temp = write('template.json', template)
    obs = []
    for i, judgment in enumerate(judgments):
        obs.append(write(f'judgment_observables_{i:02d}.json', {
            'template_id': template['template_id'], 'phrase': judgment['phrase'],
            'note': judgment['note'], 'status': 'draft',
            'observable_requirements': {
                'observables': [{'name': 'engine_running', 'unit': 'categorical',
                                 'description': 'Original engine operation across unattended stand'},
                                {'name': 'parking_brake_set', 'unit': 'categorical',
                                 'description': 'Original brake readback and holding review'},
                                {'name': 'front_wheel_heading_to_curb_deg', 'unit': 'deg',
                                 'description': 'Calibrated original wheel orientation'},
                                {'name': 'unattended_interval', 'unit': 'categorical',
                                 'description': 'Identified attendance and cabin state'}],
                'context_inputs': [],
                'landmarks': [],
                'recording_needs': [{'name': 'engine_running', 'unit': 'categorical',
                                     'description': 'Retain original operation source and same-frame join'},
                                    {'name': 'parking_brake_set', 'unit': 'categorical',
                                     'description': 'Retain original brake readback'},
                                    {'name': 'front_wheel_heading_to_curb_deg', 'unit': 'deg',
                                     'description': 'Retain calibrated original wheel source'},
                                    {'name': 'unattended_interval', 'unit': 'categorical',
                                     'description': 'Retain original attendance source'}],
                'sweep_dimensions': [],
                'limitations': ['Synthetic fixtures test software only; legal judgment and physical state need independent original review.']}}))
    bindings = {'cell_id': 'C276263', 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [{'name': 'sloped_highway_stand_candidate',
                                  'source': 'Frozen C276263 cell and original map survey; highway status and perceptibility remain for review'}],
        'law_refs': [{'template_id': template['template_id'], 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [{**p, 'used_by_laws': [LAW]} for p in parameters]}
    bind = write('bindings.json', bindings)
    cases = {'path': 'proposals/cases.json', 'sha256': sha(OUT / 'cases.json')}
    index = {'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
             'stages': {'relevance_batch': batch, 'relevance': rel,
                        'template': temp, 'judgment_observables': obs,
                        'bindings': bind, 'cases': cases}}
    write('semantic-index.json', index)
    print(sha(OUT / 'semantic-index.json'))


if __name__ == '__main__':
    build()
