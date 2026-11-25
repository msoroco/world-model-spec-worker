"""Write source-quoted signed-zone semantic proposals for local review."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = 'NRS-484B-620-2'
ACTOR = 'motor_vehicle_driver'
TEXT = 'After the establishment of a speed zone and the installation of appropriate signs to control speed, it is unlawful for any person to drive a motor vehicle upon the road and in the speed zone in excess of the speed therein authorized.'
TEMPLATE = LAW + '@' + ACTOR


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(HERE)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((HERE.parents[1] / 'inputs' / AID / 'assignment.json').read_text())
    assert assignment['law']['text'] == TEXT
    desc = json.loads((HERE / 'draft-exact/probe_01/primary/construction.json').read_text())['recording_description']
    refs = {}
    relevance = {'cell_id': 'C179819', 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
            'relevance_type': 'specific_match', 'confidence': 'high',
            'notes': 'Frozen paved road travel and motor-vehicle driver; administrative establishment and installed signs require original review.'}],
        'borderline_excluded': []}
    refs['relevance_batch'] = write(HERE / 'proposals/relevance-batch.json', relevance)
    refs['relevance'] = write(HERE / 'proposals/relevance.json', relevance)
    judgments = [
        {'phrase': 'establishment of a speed zone', 'note': 'Prior administrative establishment must come from an independent source.'},
        {'phrase': 'installation of appropriate signs to control speed', 'note': 'Installed sign face, appropriateness and direction require independent original review.'},
        {'phrase': 'speed therein authorized', 'note': 'Applicable authorized value is source-read; measured excess is not a synthetic legal verdict.'}]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'status': 'draft', 'quote': TEXT,
        'structure': {'activation': {'description': 'Prior establishment and appropriate installed speed-control signs on the governed road and direction.',
            'source_clause': 'After the establishment of a speed zone and the installation of appropriate signs to control speed'},
            'obligation': {'description': 'Measure motor-vehicle speed during signed-zone occupancy against the independently sourced authorized value; reserve legal conclusion.',
                'type': 'must', 'source_clause': 'in the speed zone in excess of the speed therein authorized',
                'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'Original Native speed is joined to each frame inside reviewed zone boundaries; no invented grace period.'},
            'judgment_calls_needed': judgments},
        'parameter_refs': [{'name': 'observed_speed_mph', 'kind': 'subject_behavior', 'range_or_domain': 'original Native velocity in mph'},
            {'name': 'authorized_mph', 'kind': 'world_setup', 'range_or_domain': 'independently sourced installed sign value'},
            {'name': 'signed_zone_bounds_m', 'kind': 'world_setup', 'range_or_domain': 'independently reviewed establishment extent'}]}
    refs['template'] = write(HERE / 'proposals/template.json', template)
    observed = []
    terms = [('dev.zone_sign', 'drv.within_signed_zone'),
             ('dev.speed_limit_sign', 'dev.governs'),
             ('kin.speed', 'rel.occupies', 'ru.motor_vehicle')]
    for i, judgment in enumerate(judgments, 1):
        names = terms[i-1]
        req = {'observables': [{'name': name, 'unit': 'm/s' if name == 'kin.speed' else 'structured',
                'description': 'Original source-joined observation of ' + name} for name in names],
            'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': name, 'unit': 'm/s' if name == 'kin.speed' else 'structured',
                'description': 'Retain original frame and source join for ' + name} for name in names],
            'limitations': ['Synthetic source shapes establish software behavior only; administrative and sign authority remain open.']}
        observed.append(write(HERE / ('proposals/judgment-%d.json' % i),
            {'template_id': TEMPLATE, 'phrase': judgment['phrase'], 'note': judgment['note'],
             'status': 'draft', 'observable_requirements': req}))
    refs['judgment_observables'] = observed
    binding = {'cell_id': 'C179819', 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [{'name': 'road_context', 'value': 'paved road travel with speed-limit sign', 'rationale': 'Frozen catalog cell.'}],
        'variable_parameters': [{'name': 'observed_speed_mph', 'kind': 'subject_behavior', 'range_or_domain': 'source-measured mph inside zone', 'used_by_laws': [LAW]},
            {'name': 'controller_speed_request_mps', 'kind': 'controller', 'range_or_domain': '20, 25, 30 mph converted to m/s', 'used_by_laws': [LAW]},
            {'name': 'authorized_mph', 'kind': 'world_setup', 'range_or_domain': 'reviewed installed sign value, held fixed across cases', 'used_by_laws': [LAW]}]}
    refs['bindings'] = write(HERE / 'proposals/bindings.json', binding)
    cases = [{'case_id': AID + '__baseline', 'target_law_id': None, 'target_type': 'baseline',
        'rationale': 'Observe frozen paved road and sign context without targeting excess speed.',
        'variable_assignments': {'observed_speed_mph': {'kind': 'subject_behavior', 'value': None},
            'controller_speed_request_mps': {'kind': 'controller', 'value': None},
            'authorized_mph': {'kind': 'world_setup', 'value': None}},
        'unresolved_judgment_calls': [j['phrase'] for j in judgments], 'recording_description': desc}]
    for suffix, label, mph in (('probe_01', 'below', 20), ('probe_02', 'at', 25), ('probe_03', 'above', 30)):
        cases.append({'case_id': AID + '__' + suffix, 'target_law_id': LAW,
            'target_type': 'boundary_probe', 'paired_probe_id': 'signed_zone_25',
            'rationale': 'Request ' + label + ' authorized speed and measure original in-zone speed without a legal label.',
            'deliberate_differences': ['controller_speed_request_mps'],
            'variable_assignments': {'observed_speed_mph': {'kind': 'subject_behavior', 'value': None},
                'controller_speed_request_mps': {'kind': 'controller', 'value': round(mph*.44704, 6)},
                'authorized_mph': {'kind': 'world_setup', 'value': 25}},
            'unresolved_judgment_calls': [j['phrase'] for j in judgments],
            'recording_description': desc,
            'probe': {'primary_variable': 'observed_speed_mph', 'comparison_or_standard': 'source-reviewed authorized sign value',
                'target_value_or_branch': label},
            'epsilon_used': {'value': 5, 'unit': 'mph', 'rationale': 'Controlled request separation, not a legal tolerance.'}})
    specs = [{'sweep_id': 'signed-zone-authority-review', 'target_law_id': LAW,
        'judgment_refs': judgments, 'status': 'incomplete',
        'rationale': 'Synthetic diagnostics preserve data joins while official authority and legal outcome remain open.',
        'missing_inputs': ['Independent administrative establishment and installed sign review from original sources.']}]
    refs['cases'] = write(HERE / 'proposals/cases.json', {'cell_id': 'C179819', 'actor': ACTOR,
        'status': 'draft', 'sweep_specs': specs, 'sweeps_expanded': True, 'cases': cases})
    write(HERE / 'proposals/semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': AID, 'stages': refs})


if __name__ == '__main__':
    main()
