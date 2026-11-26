"""Source-quoted controlled-access entry semantic proposals for local review."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = 'NRS-484B-587-1'
ACTOR = 'motor_vehicle_driver'
ASSIGNMENT = json.loads((HERE.parents[1] / 'inputs' / AID / 'assignment.json').read_text())
TEXT = ASSIGNMENT['law']['text']
TEMPLATE = LAW + '@' + ACTOR


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    refs = {}
    relevance = {'cell_id': 'C228131', 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
            'relevance_type': 'specific_match', 'confidence': 'low',
            'notes': 'Frozen enter_road cell supports only the onto-highway branch if original controlled-access, public authority, device and entrance sources are established.'}],
        'borderline_excluded': []}
    refs['relevance_batch'] = write(HERE / 'proposals/relevance-batch.json', relevance)
    refs['relevance'] = write(HERE / 'proposals/relevance.json', relevance)
    judgments = [
        {'phrase': 'controlled-access highway', 'note': 'Original public-authority access determination, highway dedication, public use and boundaries require independent sources.'},
        {'phrase': 'official traffic-control devices are erected giving notice', 'note': 'Original official authority, installed sign, content, notice and indicated extent require separate sources.'},
        {'phrase': 'onto or from', 'note': 'The onto branch has an entry pair; from requires an exit-road frozen binding unavailable here.'}]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'status': 'draft', 'quote': TEXT,
        'structure': {'activation': {'description': 'Original motor vehicle driving to a source-established controlled-access highway under erected official device notice.',
            'source_clause': 'When official traffic-control devices are erected giving notice thereof'},
            'obligation': {'description': 'Review original entry point against indicated entrances and, in a separate eligible cell, exit point against indicated exits.',
                'type': 'must_not', 'source_clause': 'shall not drive a vehicle onto or from any controlled-access highway except at those entrances and exits which are indicated by such devices',
                'numeric_conditions': []},
            'exceptions': [], 'timing': {'description': 'Retain original body trajectory and road boundary across the entry point; no invented statutory footprint crossing cutoff.'},
            'judgment_calls_needed': judgments},
        'parameter_refs': [{'name': 'controlled_access_and_device_context', 'kind': 'world_setup',
            'range_or_domain': 'independently reviewed public authority and official device sources'},
            {'name': 'requested_crossing_x_m', 'kind': 'controller',
             'range_or_domain': '0 or 60 m relative to sourced indicated entrance'},
            {'name': 'measured_entry_point', 'kind': 'subject_behavior',
             'range_or_domain': 'original body/frame crossing point'}]}
    refs['template'] = write(HERE / 'proposals/template.json', template)
    observed = []
    for index, (judgment, name) in enumerate(zip(judgments,
            ('st.controlled_access', 'dev.regulatory_sign', 'kin.position')), 1):
        req = {'observables': [{'name': name, 'unit': 'structured',
                'description': 'Original source-joined observation of ' + name}],
            'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': name, 'unit': 'structured',
                'description': 'Retain original source and independent review for ' + name}],
            'limitations': ['Synthetic context and pixels exercise software joins only; authority, physical realization and legal outcome remain open.']}
        observed.append(write(HERE / ('proposals/judgment-%d.json' % index),
            {'template_id': TEMPLATE, 'phrase': judgment['phrase'], 'note': judgment['note'],
             'status': 'draft', 'observable_requirements': req}))
    refs['judgment_observables'] = observed
    binding = {'cell_id': 'C228131', 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [{'name': 'authored_highway_entrance_context',
            'value': 'same highway, frontage, paved entrance and candidate device in both entry cases',
            'rationale': 'Frozen enter_road cell; original controlled-access and official status remain for review.'}],
        'variable_parameters': [{'name': 'measured_entry_point', 'kind': 'subject_behavior',
            'range_or_domain': 'original body crossing location', 'used_by_laws': [LAW]},
            {'name': 'requested_crossing_x_m', 'kind': 'controller',
             'range_or_domain': '0 or 60 m crossing request', 'used_by_laws': [LAW]},
            {'name': 'controlled_access_and_device_context', 'kind': 'world_setup',
             'range_or_domain': 'separate original access and device authority review', 'used_by_laws': [LAW]}]}
    refs['bindings'] = write(HERE / 'proposals/bindings.json', binding)
    desc = json.loads((HERE / 'draft-exact/witness_1/primary/construction.json').read_text())['recording_description']
    cases = [{'case_id': AID + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Observe authored road and device without a selected entry target.',
        'variable_assignments': {'measured_entry_point': {'kind': 'subject_behavior', 'value': None},
            'requested_crossing_x_m': {'kind': 'controller', 'value': None},
            'controlled_access_and_device_context': {'kind': 'world_setup', 'value': 'review_pending'}},
        'unresolved_judgment_calls': [j['phrase'] for j in judgments],
        'recording_description': desc}]
    for suffix, x in (('witness_1', 0), ('witness_2', 60)):
        cases.append({'case_id': AID + '__' + suffix, 'target_law_id': LAW,
            'target_type': 'boundary_probe', 'paired_probe_id': 'controlled_entry_pair',
            'rationale': 'Request a measured onto-highway crossing ' +
                         ('at' if x == 0 else 'away from') + ' the sourced indicated entrance.',
            'deliberate_differences': ['requested_crossing_x_m'],
            'variable_assignments': {'measured_entry_point': {'kind': 'subject_behavior', 'value': None},
                'requested_crossing_x_m': {'kind': 'controller', 'value': x},
                'controlled_access_and_device_context': {'kind': 'world_setup', 'value': 'review_pending'}},
            'unresolved_judgment_calls': [j['phrase'] for j in judgments],
            'recording_description': desc,
            'probe': {'primary_variable': 'measured_entry_point',
                'comparison_or_standard': 'original source-reviewed indicated entrance',
                'target_value_or_branch': suffix}})
    refs['cases'] = write(HERE / 'proposals/cases.json', {'cell_id': 'C228131',
        'actor': ACTOR, 'status': 'draft', 'sweep_specs': [{'sweep_id': 'access-authority-review',
            'target_law_id': LAW, 'judgment_refs': judgments, 'status': 'incomplete',
            'rationale': 'Source-shaped entry diagnostics retain the entry point while original public access and device authority remain for review.',
            'missing_inputs': ['Original controlled-access designation, public authority and installed official-device sources; frozen exit-road cell binding.']}],
        'sweeps_expanded': True, 'cases': cases})
    write(HERE / 'proposals/semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': AID, 'stages': refs})


if __name__ == '__main__':
    main()
