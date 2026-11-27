"""Build source-quoted canonical semantic proposals for the selected branch pair."""
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from batch_pipeline.store import digest
assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
source = json.loads((ROOT / 'proposals/cases.json').read_text())
law, cell, actor = assignment['law'], assignment['cell'], assignment['actor']
law_id = law['id']
template_id = law_id + '@' + actor
out = ROOT / 'proposals'


def write(name, value):
    path = out / name
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    return {'path': 'proposals/' + name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {'cell_id': cell['cell_id'], 'actor': actor, 'status': 'draft',
             'relevant_laws': [{'law_id': law_id, 'quote': law['text'],
                                'applies_to': [actor], 'relevance_type': 'specific_match',
                                'confidence': 'high', 'notes': 'Selected inoperative signal branch; legal judgment remains open.'}],
             'borderline_excluded': []}
refs = {'relevance_batch': write('relevance_batch.json', relevance),
        'relevance': write('relevance.json', relevance)}
phrase = 'proceed cautiously'
note = 'Qualitative cautious entry after the required stop; no numeric legal threshold.'
template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
            'status': 'draft', 'quote': law['text'],
            'structure': {
                'activation': {'condition': 'Vehicle enters an intersection with an installed, uncovered, inoperative vehicular signal.',
                               'source_clause': 'installed and has its vehicular signals uncovered, but is inoperative',
                               'numeric_conditions': []},
                'obligation': {'type': 'must', 'description': 'Stop before the near-side crosswalk when no stop line exists; then proceed cautiously and yield to prior-stopped or intersection traffic.',
                               'source_clause': 'shall stop at a clearly marked stop line or, if there is none, before entering the crosswalk on the near side of the intersection',
                               'numeric_conditions': []},
                'exceptions': [],
                'timing': {'description': 'Stop before crosswalk entry and assess yielding after the stop.',
                           'numeric_conditions': []},
                'judgment_calls_needed': [{'phrase': phrase, 'note': note}]},
            'parameter_refs': []}
refs['template'] = write('template.json', template)
observables = [{'name': name, 'unit': unit, 'description': desc} for name, unit, desc in (
    ('st.crosswalk', 'structured', 'Source-joined ego front position relative to surveyed near-side crosswalk.'),
    ('kin.velocity', 'structured', 'Original measured ego velocity.'),
    ('drv.arrival_order', 'structured', 'Original other vehicle stop and intersection occupancy history.'),
    ('dev.traffic_signal', 'structured', 'Native signal actor and governed-lane readback.'))]
judgment = {'template_id': template_id, 'phrase': phrase, 'note': note,
            'status': 'draft', 'observable_requirements': {
                'observables': observables,
                'context_inputs': [],
                'sweep_dimensions': [{'name': 'complete_halt_before_applicable_boundary',
                                      'unit': 'boolean', 'description': 'Halt versus rolling contrast at the selected crosswalk.'}],
                'landmarks': [], 'recording_needs': observables,
                'limitations': ['Original motion, signal pixels and cautiousness require independent review.']}}
refs['judgment_observables'] = [write('judgment_observables_cautious.json', judgment)]
parameters = [
    ('signal_and_crosswalk_layout', 'world_setup', 'Installed uncovered inoperative signal; no stop line; near-side crosswalk.'),
    ('commanded_stop_policy', 'controller', 'Halt request versus rolling contrast; actual halt remains measured.'),
    ('complete_halt_before_applicable_boundary', 'subject_behavior', 'Observed halt versus rolling contrast.'),
    ('commanded_ego_speed', 'controller', 'Requested approach speed; actual velocity remains trace measured.'),
    ('ego_speed', 'subject_behavior', 'Source measured m/s.'),
    ('priority_vehicle_history', 'subject_behavior', 'Other vehicle stop and occupancy history.'),
]
bindings = {'cell_id': cell['cell_id'], 'actor': actor, 'status': 'draft',
            'established_contexts': [{'name': 'inoperative_signal_crosswalk',
                                      'source': 'frozen selected NRS 484B.250(4) catalog cell'}],
            'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
            'context_refs': [], 'fixed_parameters': [],
            'variable_parameters': [{'name': n, 'kind': k, 'range_or_domain': d,
                                     'used_by_laws': [law_id]} for n, k, d in parameters]}
refs['bindings'] = write('bindings.json', bindings)
kind = {n: k for n, k, _ in parameters}
cases = copy.deepcopy(source)
cases['cases'] = [item for item in cases['cases'] if not item['case_id'].endswith('__baseline')]
for item in cases['cases']:
    halt = item['case_id'].endswith('witness_1')
    item['variable_assignments'] = {
        'signal_and_crosswalk_layout': {'kind': kind['signal_and_crosswalk_layout'], 'value': 'surveyed selected layout'},
        'commanded_stop_policy': {'kind': kind['commanded_stop_policy'], 'value': 0.0 if halt else 1.0},
        'complete_halt_before_applicable_boundary': {'kind': kind['complete_halt_before_applicable_boundary'], 'value': None},
        'commanded_ego_speed': {'kind': kind['commanded_ego_speed'], 'value': 6.0, 'unit': 'm/s'},
        'ego_speed': {'kind': kind['ego_speed'], 'value': None},
        'priority_vehicle_history': {'kind': kind['priority_vehicle_history'], 'value': None}}
    item['unresolved_judgment_calls'] = [phrase]
    item['target_type'] = 'judgment_sweep'
    item['paired_probe_id'] = ROOT.name + '__halt_sweep'
    item['deliberate_differences'] = ['commanded_stop_policy']
    item['probe'] = {'primary_variable': 'commanded_stop_policy',
                     'comparison_or_standard': 'physical halt coverage; legal caution unresolved',
                     'target_value_or_branch': {'commanded_stop_policy': 0.0 if halt else 1.0}}
    item['sweep_id'] = ROOT.name + '__halt_sweep'
    item['sweep_point'] = {'commanded_stop_policy': 0.0 if halt else 1.0}
spec = {'sweep_id': ROOT.name + '__halt_sweep', 'target_law_id': law_id,
        'judgment_refs': [{'phrase': phrase, 'note': note}],
        'rationale': 'Two requested stop policies at one selected near-side crosswalk; no legal threshold.',
        'status': 'complete', 'mode': 'one_dimensional',
        'axes': [{'variable': 'commanded_stop_policy',
                  'observable': 'complete_halt_before_applicable_boundary', 'unit': 'boolean',
                  'min': 0.0, 'max': 1.0, 'spacing': 1.0,
                  'range_rationale': 'Two exact authored controller policies: halt request and roll request.',
                  'spacing_rationale': 'One code step distinguishes the two requested policies.',
                  'feasibility_evidence': 'Both 600-frame constructions pass CPU offline and diagnostic compatibility; Native motion pending.',
                  'measurement': {'method': 'source-joined ego speed and crosswalk boundary order',
                                  'time_window': '30 s', 'statistic': 'max'}}],
        'landmarks': [], 'variable_assignments': copy.deepcopy(cases['cases'][0]['variable_assignments']),
        'recording_description': copy.deepcopy(cases['cases'][0]['recording_description'])}
spec['spec_version'] = digest(spec)
spec['planned_case_count'] = 2
spec['selection_order'] = [item['case_id'] for item in cases['cases']]
cases['sweep_specs'] = [spec]
for item in cases['cases']:
    item['sweep_spec_version'] = spec['spec_version']
cases['status'] = 'draft'
baseline = copy.deepcopy(cases['cases'][0])
baseline['case_id'] = ROOT.name + '__baseline'
baseline['target_law_id'] = None
baseline['target_type'] = 'baseline'
baseline['rationale'] = 'Shared authored signal and crosswalk setup; no baseline recording selected.'
cases['cases'].insert(0, baseline)
refs['cases'] = write('canonical-cases.json', cases)
write('cases.json', cases)
write('semantic-index.json', {'format': 'worker-semantic-delivery',
                              'assignment_id': ROOT.name, 'stages': refs})
