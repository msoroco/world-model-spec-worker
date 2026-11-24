"""Build planned physical judgment sweeps without legal outcome labels.

All ranges are source-bound synthetic planning targets. Native realization and
statutory judgments remain unknown until original local review.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))
from scenario_pipeline.batch_pipeline.sweeps import expand_sweeps
from scenario_pipeline.batch_pipeline.validation import coverage, observable_requirements

PROPOSALS = HERE / 'proposals'
LAW = 'LVMC-11-16-090-A'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name):
    return json.loads((PROPOSALS / name).read_text())


def write(name, value):
    (PROPOSALS / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def parameter(name, kind, unit):
    return {'name': name, 'kind': kind,
            'range_or_domain': 'Physical source in ' + unit + '; actual Native value initially unknown',
            'used_by_laws': [LAW]}


def assignment(kind, unit, value):
    return {'kind': kind, 'unit': unit, 'value': value}


def channel(name, unit, method):
    return {'name': name, 'unit': unit, 'sampling_rate_hz': 20,
            'method': method, 'time_window': 'all 600 original frames',
            'reference_frame': 'original Native map and vehicle',
            'uncertainty': '20 Hz frame bracket and source map projection'}


def main():
    ranges = json.loads((HERE / 'sweep-physical/planned-ranges.json').read_text())
    proof = json.loads((HERE / 'sweep-physical/native-helper-proof.json').read_text())
    if proof['source_range_sha256'] != sha(HERE / 'sweep-physical/planned-ranges.json'):
        raise ValueError('Physical source plan changed')
    template = load('template.json')
    judgments = [load('judgment-observables-1.json'), load('judgment-observables-2.json')]
    binding = load('bindings.json')
    cases = load('cases.json')
    # Expansion is deterministic, and this builder may be rerun after a CPU
    # validator points out a downstream binding. Retain only authored cases.
    cases['cases'] = [case for case in cases['cases']
                      if case.get('target_type') != 'judgment_sweep']
    new = [
        parameter('commanded_acceleration_mps2', 'controller', 'm/s2'),
        parameter('ego_acceleration', 'subject_behavior', 'm/s2'),
        parameter('requested_route_offset_m', 'world_setup', 'm'),
        parameter('route_position_m', 'subject_behavior', 'm'),
    ]
    for param in new:
        if param['name'] not in {p['name'] for p in binding['variable_parameters']}:
            binding['variable_parameters'].append(copy.deepcopy(param))
        if param['name'] not in {p['name'] for p in template['parameter_refs']}:
            template['parameter_refs'].append({k: param[k] for k in ('name', 'kind', 'range_or_domain')})
    for case in cases['cases']:
        values = case['variable_assignments']
        values['commanded_acceleration_mps2'] = assignment('controller', 'm/s2', None)
        values['ego_acceleration'] = assignment('subject_behavior', 'm/s2', None)
        values['requested_route_offset_m'] = assignment('world_setup', 'm', None)
        values['route_position_m'] = assignment('subject_behavior', 'm', None)
    dimensions = [
        {'name': 'ego_acceleration', 'unit': 'm/s2',
         'description': 'Original longitudinal acceleration measured separately from the controller request.'},
        {'name': 'route_position_m', 'unit': 'm',
         'description': 'Original vehicle position projected onto the original mapped route; no highway classification.'},
    ]
    judgments[0]['observable_requirements']['sweep_dimensions'] = [dimensions[0]]
    judgments[1]['observable_requirements']['sweep_dimensions'] = [dimensions[1]]
    for judgment in judgments:
        observable_requirements(judgment['observable_requirements'])
    source = ranges['fixture_sha256']
    base = copy.deepcopy(cases['cases'][1]['variable_assignments'])
    base['commanded_acceleration_mps2']['value'] = 0.1
    base['requested_route_offset_m']['value'] = 25.0
    rec = copy.deepcopy(cases['cases'][1]['recording_description'])
    rec['channels'].append(channel('route_position_m', 'm',
                                   'original ego pose projected onto source-hashed original road geometry'))
    acceleration = {
        'sweep_id': HERE.name + '__judgment-1', 'target_law_id': LAW,
        'judgment_refs': copy.deepcopy(cases['sweep_specs'][0]['judgment_refs']),
        'status': 'complete', 'mode': 'one_dimensional',
        'axes': [{'variable': 'commanded_acceleration_mps2',
                  'observable': 'ego_acceleration', 'unit': 'm/s2',
                  'min': 0.1, 'max': 0.2, 'spacing': 0.05,
                  'measurement': {'method': 'original Native longitudinal acceleration vector',
                                  'time_window': 'frames 160 through 439, excluding startup',
                                  'statistic': 'max'},
                  'range_rationale': 'Brackets 0.1 and 0.2 m/s2 in source-hashed reference and contrast synthetic traces; engineering planning only.',
                  'spacing_rationale': 'One interior target separates endpoints without implying a legal cutoff.',
                  'feasibility_evidence': 'sweep-physical/planned-ranges.json and native-helper-proof.json; Native response remains unverified.'}],
        'landmarks': [],
        'rationale': 'Sample requested longitudinal acceleration targets while measuring actual Native acceleration and preserving exhibition as unknown.',
        'variable_assignments': copy.deepcopy(base),
        'recording_description': copy.deepcopy(rec),
    }
    route = {
        'sweep_id': HERE.name + '__judgment-2', 'target_law_id': LAW,
        'judgment_refs': copy.deepcopy(cases['sweep_specs'][1]['judgment_refs']),
        'status': 'complete', 'mode': 'one_dimensional',
        'axes': [{'variable': 'requested_route_offset_m',
                  'observable': 'route_position_m', 'unit': 'm',
                  'min': 25.0, 'max': 175.0, 'spacing': 75.0,
                  'measurement': {'method': 'original vehicle pose joined to source-hashed road geometry',
                                  'time_window': 'all 600 original frames',
                                  'statistic': 'first'},
                  'range_rationale': '25 to 175 m stays inside the 300 m source-hashed synthetic road and observed 0 to 209.5 m reference path; highway status remains unknown.',
                  'spacing_rationale': 'Three separated route origins cover a finite engineering path span without a legal cutoff.',
                  'feasibility_evidence': 'sweep-physical/planned-ranges.json and native-helper-proof.json; Native route existence remains unverified.'}],
        'landmarks': [],
        'rationale': 'Sample route positions on an authored centerline while recording original map and jurisdiction sources; statutory highway status remains unknown.',
        'variable_assignments': copy.deepcopy(base),
        'recording_description': copy.deepcopy(rec),
    }
    cases['sweep_specs'] = [acceleration, route]
    cases['sweeps_expanded'] = False
    expand_sweeps(cases, [template], binding)
    assembled = copy.deepcopy(template)
    for target, source in zip(assembled['structure']['judgment_calls_needed'], judgments):
        target['observable_requirements'] = source['observable_requirements']
    coverage(cases['cases'], binding, [assembled], cases['sweep_specs'])
    write('template.json', template)
    write('judgment-observables-1.json', judgments[0])
    write('judgment-observables-2.json', judgments[1])
    write('bindings.json', binding)
    write('cases.json', cases)
    index = load('semantic-index.json')
    for key, filename in [('template', 'template.json'), ('bindings', 'bindings.json'),
                          ('cases', 'cases.json')]:
        index['stages'][key]['sha256'] = sha(PROPOSALS / filename)
    for i in range(2):
        index['stages']['judgment_observables'][i]['sha256'] = sha(PROPOSALS / f'judgment-observables-{i+1}.json')
    write('semantic-index.json', index)
    print(json.dumps({'semantic_index_sha256': sha(PROPOSALS / 'semantic-index.json'),
                      'cases': len(cases['cases']), 'sweeps': len(cases['sweep_specs'])}))


if __name__ == '__main__':
    main()
