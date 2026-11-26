"""Draft source-quoted rail-stop semantic stages for local review."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = 'NRS-484B-557'
ACTOR = 'motor_vehicle_driver'
ASSIGNMENT = json.loads((HERE.parents[1] / 'inputs' / AID / 'assignment.json').read_text())
TEXT = ASSIGNMENT['law']['text']
TEMPLATE = LAW + '@' + ACTOR
TARGETS = {'probe_1': 25, 'probe_2': 10, 'probe_3': 15,
           'probe_4': 50, 'probe_5': 50.5}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    refs = {}
    relevance = {'cell_id': 'C25835', 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
            'relevance_type': 'specific_match', 'confidence': 'low',
            'notes': 'Frozen blind_rail_crossing/cross_railway/stop_sign cell. Original official designation, sign governance and physical crossing remain for review.'}],
        'borderline_excluded': []}
    refs['relevance_batch'] = write(HERE / 'proposals/relevance-batch.json', relevance)
    refs['relevance'] = write(HERE / 'proposals/relevance.json', relevance)
    judgments = [
        {'phrase': 'designate dangerous highway grade crossings of railroads',
         'note': 'Department of Transportation designation or local authority with Department approval requires an original administrative source.'},
        {'phrase': 'erect official traffic-control devices at such crossings directing a stop',
         'note': 'Original installed official stop sign and approach governance require separate source review.'},
        {'phrase': 'within 50 feet but not less than 15 feet from the nearest track',
         'note': 'Original nearest-track and vehicle geometry yield front, centre and rear distances; the statute does not specify a vehicle reference point.'},
        {'phrase': 'afterward may proceed only upon exercising due care',
         'note': 'Retain motion, visibility, occluder and actual train state; no numerical due-care substitute.'}]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'status': 'draft', 'quote': TEXT,
        'structure': {'activation': {'description': 'Source-established dangerous highway railroad grade crossing with official erected stop sign governing the subject approach.',
            'source_clause': 'When such stop signs are erected'},
            'obligation': {'description': 'Observe complete cessation within the statutory distance band from the nearest track before proceeding.',
                'type': 'must',
                'source_clause': 'shall stop within 50 feet but not less than 15 feet from the nearest track',
                'numeric_conditions': [{'name': 'outer_distance_ft', 'value': 50},
                                       {'name': 'inner_distance_ft', 'value': 15}]},
            'exceptions': [],
            'timing': {'description': 'Original stop precedes proceeding; no statutory stop duration.'},
            'judgment_calls_needed': judgments},
        'parameter_refs': [{'name': 'official_rail_crossing_context', 'kind': 'world_setup',
            'range_or_domain': 'independent original designation and sign authority sources'},
            {'name': 'requested_stop_center_ft', 'kind': 'controller',
             'range_or_domain': '10, 15, 25, 50 or 50.5 ft centre request'},
            {'name': 'observed_stop_distances_ft', 'kind': 'subject_behavior',
             'range_or_domain': 'original front, centre and rear source-joined distances'}]}
    refs['template'] = write(HERE / 'proposals/template.json', template)
    observed = []
    for index, (judgment, name) in enumerate(zip(judgments,
            ('st.railway_crossing', 'dev.stop_sign', 'rel.centre_distance',
             'drv.stopped')), 1):
        req = {'observables': [{'name': name, 'unit': 'structured',
                'description': 'Original source-joined observation of ' + name}],
            'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': name, 'unit': 'structured',
                'description': 'Retain original source and independent review for ' + name}],
            'limitations': ['Synthetic context and pixels exercise software joins only; administrative authority, physical realization, due care and legal outcome remain open.']}
        observed.append(write(HERE / ('proposals/judgment-%d.json' % index),
            {'template_id': TEMPLATE, 'phrase': judgment['phrase'],
             'note': judgment['note'], 'status': 'draft',
             'observable_requirements': req}))
    refs['judgment_observables'] = observed
    binding = {'cell_id': 'C25835', 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [],
        'fixed_parameters': [{'name': 'authored_grade_crossing_context',
            'value': 'same road, rails, sign, occluder, vehicle, cameras and controller policy',
            'rationale': 'Frozen blind-rail-crossing cell; original authority and physics remain for review.'}],
        'variable_parameters': [{'name': 'observed_stop_distances_ft',
            'kind': 'subject_behavior', 'range_or_domain': 'original front, centre and rear feet',
            'used_by_laws': [LAW]},
            {'name': 'requested_stop_center_ft', 'kind': 'controller',
             'range_or_domain': '10, 15, 25, 50 or 50.5 ft', 'used_by_laws': [LAW]},
            {'name': 'official_rail_crossing_context', 'kind': 'world_setup',
             'range_or_domain': 'distinct original designation, sign and crossing review',
             'used_by_laws': [LAW]}]}
    refs['bindings'] = write(HERE / 'proposals/bindings.json', binding)
    desc = json.loads((HERE / 'draft-native/probe_1/primary/construction.json').read_text())['recording_description']
    cases = [{'case_id': AID + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Unselected neutral crossing context.',
        'variable_assignments': {'observed_stop_distances_ft': {'kind': 'subject_behavior', 'value': None},
            'requested_stop_center_ft': {'kind': 'controller', 'value': None},
            'official_rail_crossing_context': {'kind': 'world_setup', 'value': 'review_pending'}},
        'unresolved_judgment_calls': [j['phrase'] for j in judgments],
        'recording_description': desc}]
    for suffix, feet in TARGETS.items():
        cases.append({'case_id': AID + '__' + suffix, 'target_law_id': LAW,
            'target_type': 'boundary_probe', 'paired_probe_id': 'rail_stop_boundary_sweeps',
            'rationale': 'Request source-measured cessation ' + str(feet) +
                         ' ft from nearest rail by vehicle centre, retaining all vehicle reference points.',
            'deliberate_differences': ['requested_stop_center_ft'],
            'variable_assignments': {'observed_stop_distances_ft': {'kind': 'subject_behavior', 'value': None},
                'requested_stop_center_ft': {'kind': 'controller', 'value': feet},
                'official_rail_crossing_context': {'kind': 'world_setup', 'value': 'review_pending'}},
            'unresolved_judgment_calls': [j['phrase'] for j in judgments],
            'recording_description': desc,
            'probe': {'primary_variable': 'observed_stop_distances_ft',
                'comparison_or_standard': 'original source-reviewed nearest track',
                'target_value_or_branch': str(feet) + ' ft centre request'}})
    refs['cases'] = write(HERE / 'proposals/cases.json', {'cell_id': 'C25835',
        'actor': ACTOR, 'status': 'draft',
        'sweep_specs': [{'sweep_id': 'rail-stop-distance-boundaries',
            'target_law_id': LAW, 'judgment_refs': judgments, 'status': 'incomplete',
            'rationale': 'Source-shaped boundary diagnostics retain original stop geometry; authority and due care remain for review.',
            'missing_inputs': ['Original designation, official sign and physical crossing source reviews.']}],
        'sweeps_expanded': True, 'cases': cases})
    write(HERE / 'proposals/semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': AID, 'stages': refs})


if __name__ == '__main__':
    main()
