"""Write source-quoted access-park frontage semantic stages for local review."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = 'LVMC-11-52-305-A'
ACTOR = 'heavy_vehicle_driver'
TEXT = 'Except as otherwise provided in this Section or as permitted by posted sign, it is unlawful for a person to stand, park or store, upon any street adjacent to a residence district, public school or public park, a commercial vehicle, recreational vehicle, trailer, or any combination of vehicle and trailer having an overall length of twenty-four feet or more or an unladen weight in excess of eight thousand pounds. For purposes of the preceding sentence, a "residence district" means the territory contiguous to a street, not comprising a business district, in which the parcels abutting such street for a distance of three hundred feet or more are mainly occupied by dwellings or by dwellings and buildings in use for residence. The provisions of Subsection (A) do not apply to a commercial vehicle that is: (1) Parked in front of property from which or to which goods or passengers are being picked up or delivered, but only for that period of time during which goods or passengers are being expeditiously loaded or unloaded; or (2) Being used in conjunction with the performance of service, repair, construction or similar essential use within the immediate neighborhood.'
TEMPLATE = LAW + '@' + ACTOR


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(HERE)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((HERE.parents[1] / 'inputs' / AID / 'assignment.json').read_text())
    assert assignment['law']['text'] == TEXT
    desc = json.loads((HERE / 'draft-exact/probe_1/primary/construction.json').read_text())['recording_description']
    refs = {}
    relevance = {'cell_id': 'C135709', 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
            'relevance_type': 'specific_match', 'confidence': 'high',
            'notes': 'Frozen public-access premises and park maneuver; official park frontage designation and activity require independent source review.'}],
        'borderline_excluded': []}
    refs['relevance_batch'] = write(HERE / 'proposals/relevance-batch.json', relevance)
    refs['relevance'] = write(HERE / 'proposals/relevance.json', relevance)
    judgments = [
        {'phrase': 'public park', 'note': 'Official park frontage designation, contrasting marking or paving, adjacent designated accessible space, ingress/egress and route connectivity require independent sources; conditional 11.52.135(A) sign route requires sign details.'},
        {'phrase': 'stand, park or store', 'note': 'Vehicle, responsible person, occupancy, loading purpose and actual activity require independent review; no invented duration cutoff.'},
        {'phrase': 'permitted by posted sign', 'note': 'Public-access jurisdiction and premises context require independent original review.'}]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'status': 'draft', 'quote': TEXT,
        'structure': {'activation': {'description': 'Vehicle and responsible person at a source-reviewed qualifying public park frontage on public-access premises.',
            'source_clause': 'a vehicle in an public park frontage'},
            'obligation': {'description': 'Observe parked activity and original body footprint relative to qualifying park frontage; reserve legal conclusion.',
                'type': 'must_not', 'source_clause': 'No person shall park', 'numeric_conditions': []},
            'exceptions': [], 'timing': {'description': 'Original stationary/body observations over 600 frames; no statutory duration or overlap cutoff inferred.'},
            'judgment_calls_needed': judgments},
        'parameter_refs': [{'name': 'park_frontage_overlap', 'kind': 'subject_behavior', 'range_or_domain': 'original Native body corners against reviewed park frontage'},
            {'name': 'access_park frontage_designation', 'kind': 'world_setup', 'range_or_domain': 'independent designation and pixels'},
            {'name': 'parked_classification', 'kind': 'subject_behavior', 'range_or_domain': 'independent source review'}]}
    refs['template'] = write(HERE / 'proposals/template.json', template)
    terms = [('park_frontage_geometry',),
             ('vehicle_pose_and_speed',), ('source_camera_frame_join',)]
    observed = []
    for i, judgment in enumerate(judgments, 1):
        names = terms[i - 1]
        req = {'observables': [{'name': name, 'unit': 'structured',
                'description': 'Original source-joined observation of ' + name} for name in names],
            'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': name, 'unit': 'structured',
                'description': 'Retain original frame and independent review join for ' + name} for name in names],
            'limitations': ['Synthetic pixels and source-shaped reviews establish software behavior only; official classification and legal outcome remain open.']}
        observed.append(write(HERE / ('proposals/judgment-%d.json' % i),
            {'template_id': TEMPLATE, 'phrase': judgment['phrase'], 'note': judgment['note'],
             'status': 'draft', 'observable_requirements': req}))
    refs['judgment_observables'] = observed
    binding = {'cell_id': 'C135709', 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [{'name': 'premises_context', 'value': 'public-access premises with public park frontage', 'rationale': 'Frozen catalog cell, subject to original review.'}],
        'variable_parameters': [{'name': 'park_frontage_overlap', 'kind': 'subject_behavior', 'range_or_domain': 'outside or inside reviewed park frontage', 'used_by_laws': [LAW]},
            {'name': 'target_station_beside_park', 'kind': 'controller', 'range_or_domain': 'outside or inside request', 'used_by_laws': [LAW]}]}
    refs['bindings'] = write(HERE / 'proposals/bindings.json', binding)
    cases = [{'case_id': AID + '__baseline', 'target_law_id': None, 'target_type': 'baseline',
        'rationale': 'Observe premises context without targeting parking activity.',
        'variable_assignments': {'park_frontage_overlap': {'kind': 'subject_behavior', 'value': None},
            'target_station_beside_park': {'kind': 'controller', 'value': None}},
        'unresolved_judgment_calls': [j['phrase'] for j in judgments], 'recording_description': desc}]
    for suffix, inside in (('probe_1', False), ('probe_2', True)):
        cases.append({'case_id': AID + '__' + suffix, 'target_law_id': LAW,
            'target_type': 'boundary_probe', 'paired_probe_id': 'access_park frontage_footprint',
            'rationale': 'Request ' + ('inside' if inside else 'outside') + ' park frontage parking and measure original stationary full-body overlap without a legal label.',
            'deliberate_differences': ['target_station_beside_park'],
            'variable_assignments': {'park_frontage_overlap': {'kind': 'subject_behavior', 'value': None},
                'target_station_beside_park': {'kind': 'controller', 'value': inside}},
            'unresolved_judgment_calls': [j['phrase'] for j in judgments],
            'recording_description': desc,
            'probe': {'primary_variable': 'park_frontage_overlap',
                'comparison_or_standard': 'source-reviewed qualifying access-park frontage extent',
                'target_value_or_branch': 'inside' if inside else 'outside'}})
    refs['cases'] = write(HERE / 'proposals/cases.json', {'cell_id': 'C135709', 'actor': ACTOR,
        'status': 'draft', 'sweep_specs': [{'sweep_id': 'public-park-parking-review',
            'target_law_id': LAW, 'judgment_refs': judgments, 'status': 'incomplete',
            'rationale': 'Synthetic diagnostics preserve source joins while official designation, public-access jurisdiction and parked classification remain open.',
            'missing_inputs': ['Independent original premises, designation and parking sources.']}],
        'sweeps_expanded': True, 'cases': cases})
    write(HERE / 'proposals/semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': AID, 'stages': refs})


if __name__ == '__main__':
    main()
