"""Draft exact red-curb case proposals without deciding legal judgments."""

import json
from pathlib import Path

from build_constructions import description
from red_curb import CASES
from source_packet import ASSIGNMENT

ROOT = Path(__file__).resolve().parent


def assignments(case):
    return {
        'vehicle_classification': {'kind': 'world_setup', 'value': case.vehicle_kind,
                                   'note': 'reviewed authoritative status, never livery alone'},
        'restricted_sign': {'kind': 'world_setup', 'value': case.sign,
                            'note': 'reviewed original sign face and authority'},
        'halt_activity': {'kind': 'world_setup', 'value': case.activity,
                          'note': 'original stop, stand or park behavior remains to be measured'},
        'activity_purpose': {'kind': 'world_setup', 'value': case.purpose,
                             'note': 'original passenger, business, mail or ordinary purpose'},
        'mail_box_adjacent': {'kind': 'world_setup', 'value': case.mail_adjacent,
                              'note': 'reviewed U.S. mail drop-box adjacency'},
        'halt_duration_target_s': {'kind': 'controller', 'value': case.duration_s,
                                   'note': 'engineering duration setpoint, measured from original event times'},
    }


def build():
    desc = description()
    baseline = {'case_id': ASSIGNMENT + '__baseline',
                'target_law_id': None, 'target_type': 'baseline',
                'rationale': 'Common municipal red edge, reviewed packet and complete original capture.',
                'variable_assignments': assignments(CASES[0]),
                'recording_description': desc,
                'unresolved_judgment_calls': ['period necessary to conduct their business',
                                              'expeditiously deposit mail']}
    cases = [baseline]
    for case in CASES:
        cases.append({'case_id': ASSIGNMENT + '__' + case.name,
                      'target_law_id': 'LVMC-11-52-030-A',
                      'target_type': 'boundary_probe',
                      'rationale': 'Observe original source-bound red-curb activity and exception facts without a legal verdict.',
                      'variable_assignments': assignments(case),
                      'recording_description': desc,
                      'unresolved_judgment_calls': ['period necessary to conduct their business',
                                                    'expeditiously deposit mail'],
                      'paired_probe_id': 'red_curb_source_comparisons',
                      'deliberate_differences': list(assignments(case)),
                      'probe': {'primary_variable': 'halt_duration_target_s',
                                'comparison_or_standard': 'LVMC 11.52.030(A) source-bound branch',
                                'target_value_or_branch': case.name}})
    proposal = {'cell_id': 'C229452', 'actor': 'motor_vehicle_driver',
                'status': 'draft', 'cases': cases, 'sweep_specs': []}
    target = ROOT / 'proposals'
    target.mkdir(exist_ok=True)
    (target / 'cases.json').write_text(json.dumps(proposal, indent=2) + '\n')
    return proposal


if __name__ == '__main__':
    print(len(build()['cases']))
