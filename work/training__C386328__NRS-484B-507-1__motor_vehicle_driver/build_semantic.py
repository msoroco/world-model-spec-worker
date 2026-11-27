"""Original-law semantic proposals for freight-zone material and passenger branches."""
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
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def reference(name):
    path = OUT / (name + '.json')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def observable(phrase, note, name, source):
    return {'template_id': TEMPLATE, 'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {
                'observables': [{'name': name, 'unit': 'structured',
                    'description': 'Original 600-frame body, sign, civil-time and four-camera measurement.'}],
                'context_inputs': [{'name': source, 'unit': 'structured',
                    'description': 'Original Native source readback plus independent full-interval review.'}],
                'sweep_dimensions': [{'name': name, 'unit': 'category',
                    'description': 'Controlled request contrast, never a legal classification.'}],
                'landmarks': [],
                'recording_needs': [{'name': name, 'unit': 'structured',
                    'description': 'Original synchronized cameras, actor bodies and sign/clock evidence.'}],
                'limitations': ['Original physical and legal judgment remain unassessed; no numeric duration cutoff is invented.']}}


def main():
    relevance = {'actor': ACTOR, 'cell_id': CELL, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': QUOTE, 'applies_to': [ACTOR],
            'relevance_type': 'direct', 'confidence': 'high',
            'notes': 'Frozen one-way freight curb cell; marking and sign authority require original review.'}],
        'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance-batch', relevance),
            'relevance': write('relevance', relevance)}
    judgments = [
        ('place marked as a freight curb loading zone during hours when the provisions applicable to such zones are in effect',
         'Authored marking and sign do not establish regulatory authority; original civil time and sign hours are source reviewed.',
         'st.curb_zone', 'sign_hours'),
        ('expeditious unloading and delivery or pickup and loading of materials',
         'Prop motion is a request; independent original activity and duration review is needed without a numeric legal cutoff.',
         'kin.extent', 'material_body'),
        ('stop temporarily ... while actually engaged in loading or unloading passengers',
         'Door and walker commands do not prove actual exchange or temporary legal character.',
         'ru.occupant_count', 'passenger_body'),
        ('does not interfere with any motor vehicle used for the transportation of materials which is waiting to enter or about to enter such zone',
         'Waiting state, vehicle class and physical interference need independent original spatial-temporal review.',
         'drv.approaching', 'waiting_vehicle_body')]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'quote': QUOTE, 'status': 'draft',
        'structure': {'activation': {'description': 'Stop, stand or park in marked freight curb zone during effective signed hours',
            'source_clause': 'in any place marked as a freight curb loading zone during hours when the provisions applicable to such zones are in effect'},
            'obligation': {'description': 'Refrain from stopping, standing or parking except for expeditious material delivery/pickup/loading',
                'type': 'must_not',
                'source_clause': 'shall not stop, stand or park a vehicle for any purpose or length of time other than for the expeditious unloading and delivery or pickup and loading of materials'},
            'exceptions': [{'description': 'Temporary actual passenger exchange without interference with a waiting or about-to-enter materials vehicle',
                'source_clause': 'The driver of a vehicle may stop temporarily at a place marked as a freight curb loading zone for the purpose of and while actually engaged in loading or unloading passengers, when such stopping does not interfere with any motor vehicle used for the transportation of materials which is waiting to enter or about to enter such zone.'}],
            'timing': {'description': 'Signed effective hours and continuous passenger/materials-vehicle interaction; no numeric legal duration threshold'},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                      for phrase, note, _, _ in judgments]},
        'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain}
                           for name, kind, domain in (
            ('material_activity_request', 'controller', ['pickup_loading', 'none_requested']),
            ('passenger_activity_request', 'controller', ['loading', 'none_requested']),
            ('signed_effective_hours', 'world_setup', ['inside', 'outside']),
            ('materials_vehicle_waiting_request', 'world_setup', [False, True]))]}
    refs['template'] = write('template', template)
    refs['judgment_observables'] = [write('judgment_observables_' + str(i),
        observable(phrase, note, name, source))
        for i, (phrase, note, name, source) in enumerate(judgments, 1)]
    binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [{'name': 'freight_curb_zone_request',
            'source': 'frozen one-way freight-zone cell and authored curb/sign readback request'}],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [{'name': name, 'kind': kind,
            'range_or_domain': domain, 'used_by_laws': [LAW]}
            for name, kind, domain in (
            ('material_activity_request', 'controller', ['pickup_loading', 'none_requested']),
            ('passenger_activity_request', 'controller', ['loading', 'none_requested']),
            ('signed_effective_hours', 'world_setup', ['inside', 'outside']),
            ('materials_vehicle_waiting_request', 'world_setup', [False, True]))]}
    refs['bindings'] = write('bindings', binding)
    refs['cases'] = reference('cases')
    path = OUT / 'semantic-index.json'
    path.write_text(json.dumps({'assignment_id': AID, 'format': 'worker-semantic-delivery',
                                'stages': refs}, indent=2, ensure_ascii=False) + '\n')
    return {'index_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'selected_cases': 5, 'judgment_observables': len(judgments)}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
