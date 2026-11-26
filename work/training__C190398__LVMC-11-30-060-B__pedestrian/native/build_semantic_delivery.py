"""Bind source-reviewed C190398 foundation to two exact selected cases."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name
OUT = ROOT/'proposals'
LAW = 'LVMC-11-30-060-B'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def main():
    constructions = {suffix: json.loads((ROOT/f'selected-{suffix}-construction.json').read_text())
                     for suffix in ('yield','enter_ahead')}
    template = json.loads((OUT/'template.json').read_text())
    unresolved = [item['phrase'] for item in template['structure']['judgment_calls_needed']]
    common_assignments = {
        'grade_separation_crossing_context': {'kind': 'world_setup', 'value': 'provided overhead crossing at measured roadway crossing point'},
        'roadway_vehicle_context': {'kind': 'world_setup', 'value': 'source-inventoried vehicle on roadway'},
        'pedestrian_yield_behavior': {'kind': 'subject_behavior', 'value': None},
        'section_070_prohibition_context': {'kind': 'world_setup', 'value': 'original authority applicability unresolved'},
        'pedestrian_departure_frame': {'kind': 'controller', 'value': None},
    }
    baseline = {'case_id': AID+'__baseline', 'target_law_id': None, 'target_type': 'baseline',
                'rationale': 'Fixed overhead crossing, roadway vehicle, weather and cameras before pedestrian departure timing varies.',
                'variable_assignments': common_assignments,
                'unresolved_judgment_calls': unresolved,
                'recording_description': constructions['yield']['recording_description']}
    cases = [baseline]
    for suffix, departure, target in (('yield',320,'compliant_attempt'),
                                       ('enter_ahead',140,'violating_attempt')):
        cases.append({'case_id': AID+'__'+suffix, 'target_law_id': LAW,
                      'target_type': 'judgment_sweep',
                      'rationale': ('Request pedestrian roadway entry after the approaching vehicle has passed' if suffix=='yield'
                                    else 'Request pedestrian entry ahead of the approaching vehicle')+
                                   '; original crossing, full vehicle inventory, overhead structure and Section 11.30.070 sources decide applicability and yield.',
                      'paired_probe_id': 'c190398-overhead-crossing-yield-pair',
                      'deliberate_differences': ['pedestrian_departure_frame'],
                      'probe': {'primary_variable':'pedestrian_departure_frame',
                                'comparison_or_standard':'source-measured pedestrian roadway entry versus every roadway vehicle passage',
                                'target_value_or_branch':str(departure)},
                      'variable_assignments': dict(common_assignments, pedestrian_departure_frame={'kind':'controller','value':departure}),
                      'unresolved_judgment_calls': unresolved,
                      'recording_description': constructions[suffix]['recording_description']})
    write(OUT/'cases.json', {'cell_id':'C190398','actor':'pedestrian','status':'draft',
                             'cases':cases,'sweep_specs':[{'sweep_id':'overhead_crossing_judgments',
                                'target_law_id': LAW,
                                'judgment_refs': template['structure']['judgment_calls_needed'],
                                'status':'incomplete',
                                'rationale':'The original overhead structure, all roadway vehicles and Section 11.30.070 authority need Native and source review before a judgment sweep can be finalized.',
                                'missing_inputs':['Original Native overpass and roadway-crossing geometry',
                                                  'Original all-vehicle interaction and municipal designated-place authority']} ]})
    foundation = json.loads((OUT/'semantic-foundation-index.json').read_text())
    stage = foundation['stages']
    refs = {key:stage[key] for key in ('relevance_batch','relevance','template','bindings')}
    refs['judgment_observables'] = [stage[f'judgment_observables_{i}'] for i in (1,2,3)]
    refs['cases'] = {'path':'proposals/cases.json','sha256':sha(OUT/'cases.json')}
    write(OUT/'semantic-index.json', {'format':'worker-semantic-delivery',
                                      'assignment_id':AID,'stages':refs})

if __name__=='__main__':
    main()
