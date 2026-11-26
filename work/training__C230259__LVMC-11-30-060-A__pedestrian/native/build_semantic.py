"""Author canonical stage proposals for the exact pedestrian yield scope."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name
DEST = ROOT / 'proposals'
DEST.mkdir(exist_ok=True)
LAW = 'LVMC-11-30-060-A'
QUOTE = ('Every pedestrian crossing a roadway at any point other than within a marked crosswalk '
         'or within an unmarked crosswalk at an intersection shall yield the right-of-way '
         'to all vehicles upon the roadway. The foregoing rules in this Section shall have '
         'no application under the conditions stated in Section 11.30.070 when pedestrians '
         'are prohibited from crossing at certain designated places.')


def write(name, obj):
    path = DEST / (name + '.json')
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')
    return path


def main():
    relevance = {'cell_id': 'C230259', 'actor': 'pedestrian', 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': QUOTE, 'applies_to': ['pedestrian'],
                           'relevance_type': 'direct', 'confidence': 'high',
                           'notes': 'Frozen travel cell has an authored roadway crossing; actual outside-crosswalk geometry and Section 11.30.070 applicability require original source review.'}],
        'borderline_excluded': []}
    write('relevance', relevance)
    write('relevance-batch', relevance)
    template = {'template_id': LAW + '@pedestrian', 'law_id': LAW,
        'actor': 'pedestrian', 'quote': QUOTE, 'status': 'draft',
        'structure': {'law_id': LAW,
            'activation': {'condition': 'pedestrian crosses roadway outside a marked or unmarked intersection crosswalk',
                           'numeric_conditions': []},
            'obligation': {'type': 'must',
                           'description': 'yield right-of-way to every vehicle upon the roadway',
                           'source_clause': 'shall yield the right-of-way to all vehicles upon the roadway.',
                           'numeric_conditions': []},
            'exceptions': [{'trigger': 'conditions stated in Section 11.30.070 prohibit pedestrian crossing at designated places',
                            'effect': 'this Section does not apply under those conditions',
                            'replacement_obligation': 'separate Section 11.30.070 source review',
                            'source_clause': 'The foregoing rules in this Section shall have no application under the conditions stated in Section 11.30.070 when pedestrians are prohibited from crossing at certain designated places.'}],
            'timing': {'description': 'throughout original crossing and every roadway vehicle interaction',
                       'numeric_conditions': []},
            'judgment_calls_needed': []},
        'parameter_refs': [{'name': 'pedestrian_departure_frame', 'kind': 'controller',
                            'range_or_domain': [140, 320]}]}
    write('template', template)
    binding = {'cell_id': 'C230259', 'actor': 'pedestrian', 'status': 'draft',
        'established_contexts': ['Authored road without marked crosswalk or junction; original Native map, pixels and designated-place prohibition require review'],
        'law_refs': [{'template_id': LAW + '@pedestrian', 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [{'name': 'pedestrian_departure_frame', 'kind': 'controller',
                                  'range_or_domain': [140, 320], 'used_by_laws': [LAW]}]}
    write('bindings', binding)
    construction = {suffix: json.loads((ROOT / ('selected-' + suffix + '-construction.json')).read_text())
                    for suffix in ('probe_01', 'probe_02')}
    baseline = {'case_id': AID + '__baseline', 'target_law_id': None, 'target_type': 'baseline',
                'rationale': 'Shared authored road and participant context before departure timing varies.',
                'variable_assignments': {'pedestrian_departure_frame': {'kind': 'controller', 'value': None}},
                'unresolved_judgment_calls': [],
                'recording_description': construction['probe_01']['recording_description']}
    cases = [baseline]
    for suffix, departure, target in (('probe_01', 320, 'compliant_attempt'),
                                       ('probe_02', 140, 'violating_attempt')):
        cases.append({'case_id': AID + '__' + suffix, 'target_law_id': LAW,
                      'target_type': target,
                      'rationale': ('Request a later pedestrian entry after roadway vehicle passage' if departure == 320
                                    else 'Request earlier pedestrian entry while the roadway vehicle approaches') +
                                   '; original source evidence and Section 11.30.070 review decide applicability and actual yield.',
                      'paired_probe_id': 'c230259-outside-crosswalk-yield-pair',
                      'deliberate_differences': ['pedestrian_departure_frame'],
                      'probe': {'primary_variable': 'pedestrian_departure_frame',
                                'comparison_or_standard': 'original pedestrian roadway entry versus all vehicle passage frames',
                                'target_value_or_branch': str(departure)},
                      'variable_assignments': {'pedestrian_departure_frame': {'kind': 'controller', 'value': departure}},
                      'unresolved_judgment_calls': [],
                      'recording_description': construction[suffix]['recording_description']})
    write('cases', {'cell_id': 'C230259', 'actor': 'pedestrian', 'status': 'draft',
                    'cases': cases, 'sweep_specs': []})
    stage_names = ('relevance-batch', 'relevance', 'template', 'bindings', 'cases')
    stages = {('relevance_batch' if name == 'relevance-batch' else name):
              {'path': 'proposals/' + name + '.json',
               'sha256': hashlib.sha256((DEST / (name + '.json')).read_bytes()).hexdigest()}
              for name in stage_names}
    stages['judgment_observables'] = []
    write('semantic-index', {'format': 'worker-semantic-delivery',
                              'assignment_id': AID, 'stages': stages})


if __name__ == '__main__':
    main()
