"""Source-preserving canonical stage draft for the supported bicycle pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'LVMC-11-40-180-A'
CELL = 'C230207'
ACTOR = 'cycle_or_scooter_operator'
TEMPLATE = LAW + '@' + ACTOR


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)), 'sha256': sha(path)}


def build():
    assignment = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
    quote = assignment['law']['text']
    relevant = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                'relevant_laws': [{'law_id': LAW, 'quote': quote, 'applies_to': [ACTOR],
                                   'relevance_type': 'direct', 'confidence': 'high',
                                   'notes': 'Exact rider prohibition and independent sign posting; all three device classes remain in scope.'}],
                'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance-batch.json', relevant),
            'relevance': write('relevance.json', relevant)}
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
                'quote': quote, 'status': 'draft',
                'structure': {'law_id': LAW,
                              'activation': {'condition': 'Person rides a bicycle, electric bicycle or electric scooter on Fremont Street sidewalk between Main and Seventh.', 'numeric_conditions': []},
                              'obligation': {'type': 'must_not', 'description': 'Do not ride those devices on that named sidewalk; the area shall separately be posted with signs stating the prohibition.', 'numeric_conditions': []},
                              'exceptions': [],
                              'timing': {'description': 'Assess whenever the device is ridden on the named sidewalk.', 'numeric_conditions': []},
                              'judgment_calls_needed': []},
                'parameter_refs': [{'name': 'requested_sidewalk_behavior', 'kind': 'controller',
                                    'range_or_domain': 'walk_cycle or mounted_sidewalk'},
                                   {'name': 'observed_rider_posture_and_occupancy', 'kind': 'subject_behavior',
                                    'range_or_domain': 'joined original rider/cycle poses, original video review or unknown'}]}
    refs['template'] = write('template.json', template)
    refs['judgment_observables'] = []
    bindings = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                'established_contexts': ['Frozen road/travel/access restriction sign cell; named geography and physical sign face require independent review.'],
                'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
                'context_refs': [], 'fixed_parameters': [],
                'variable_parameters': [
                    {'name': 'requested_sidewalk_behavior', 'kind': 'controller',
                     'range_or_domain': 'walk_cycle or mounted_sidewalk', 'used_by_laws': [LAW]},
                    {'name': 'observed_rider_posture_and_occupancy', 'kind': 'subject_behavior',
                     'range_or_domain': 'source-observed posture and sidewalk occupancy or unknown',
                     'used_by_laws': [LAW]}]}
    refs['bindings'] = write('bindings.json', bindings)
    recording = json.loads(next(f['content'] for f in json.loads((HERE / 'draft-mounted-sidewalk/walk_cycle/primary/construction.json').read_text())['files'] if f['path'] == 'config.json'))['recording_description']
    pair = AID + '__comparison'
    common = {'cell_id': CELL, 'actor': ACTOR, 'source_branch': 'Access-sign coverage and geographically specified riding',
              'comparison_variable': 'requested_sidewalk_behavior', 'requested_not_measured': True,
              'paired_probe_id': pair, 'deliberate_differences': ['requested_sidewalk_behavior'],
              'unresolved_judgment_calls': [], 'recording_description': recording}
    cases = [{'case_id': AID + '__neutral_baseline', 'target_law_id': None,
              'target_type': 'baseline', 'cell_id': CELL, 'actor': ACTOR,
              'rationale': 'Unselected common Fremont sidewalk, sign and cycle context.',
              'variable_assignments': {'requested_sidewalk_behavior': {'kind': 'controller', 'value': None},
                                       'observed_rider_posture_and_occupancy': {'kind': 'subject_behavior', 'value': None}},
              'recording_description': recording, 'unresolved_judgment_calls': []}]
    for number, behavior, target in ((1, 'walk_cycle', 'compliant_attempt'),
                                     (2, 'mounted_sidewalk', 'violating_attempt')):
        cases.append(dict(common, case_id=f'{AID}__controlled_{number}', target_law_id=LAW,
                          target_type=target,
                          variable_assignments={'requested_sidewalk_behavior': {'kind': 'controller', 'value': behavior},
                                                'observed_rider_posture_and_occupancy': {'kind': 'subject_behavior', 'value': None}},
                          probe={'primary_variable': 'requested_sidewalk_behavior',
                                 'comparison_or_standard': 'same named sidewalk, sign, bicycle and capture; requested behavior differs',
                                 'target_value_or_branch': behavior},
                          rationale='Requested ' + behavior + '; actual posture and legality require original sources'))
    proposal = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                'sweep_specs': [], 'sweeps_expanded': True, 'cases': cases}
    refs['cases'] = write('cases.json', proposal)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': AID, 'stages': refs}
    write('semantic-index.json', index)
    return {'case_ids': [c['case_id'] for c in cases], 'semantic_index_sha256': sha(HERE / 'proposals/semantic-index.json')}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
