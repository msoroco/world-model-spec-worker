"""Bind six selected exact cases to canonical unresolved-judgment proposals."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'proposals'
SHORTS = ('controlled_1', 'controlled_2', 'pedestrian_clearance',
          'pedestrian_overlap', 'concurrent_absent', 'concurrent_present')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    template = json.loads((OUT / 'template.json').read_text())
    binding = json.loads((OUT / 'bindings.json').read_text())
    phrases = [item['phrase'] for item in template['structure']['judgment_calls_needed']]
    variables = {item['name']: item['kind'] for item in binding['variable_parameters']}
    def assignments(short):
        group = 'controlled' if short.startswith('controlled_') else ('pedestrian' if short.startswith('pedestrian_') else 'concurrent')
        release = {'controlled_1': 320, 'controlled_2': 200,
                   'pedestrian_clearance': 320, 'pedestrian_overlap': 200,
                   'concurrent_absent': 220, 'concurrent_present': 220}[short]
        values = {'signal_governance': 'requested_flashing_yellow_turn_arrow_unverified',
                  'concurrent_indication': ('requested_simultaneous_left_indication' if short == 'concurrent_present'
                                             else 'no_simultaneous_left_indication_requested'),
                  'ego_turn_path': 'left' if group == 'concurrent' else 'right',
                  'ego_release_frame': release,
                  'pedestrian_lawful_status': None,
                  'other_traffic_lawful_status': None,
                  'cautious_entry_status': None}
        return {name: {'kind': kind, 'value': values[name]} for name, kind in variables.items()}
    cases = []
    base = json.loads((ROOT / 'native/selected-controlled_1-primary-construction.json').read_text())
    cases.append({'case_id': ROOT.name + '__baseline', 'target_law_id': None,
                  'target_type': 'baseline', 'rationale': 'Neutral context anchor; not a delivery capture.',
                  'variable_assignments': assignments('controlled_1'),
                  'recording_description': deepcopy(base['recording_description']),
                  'unresolved_judgment_calls': phrases})
    for short in SHORTS:
        construction = json.loads((ROOT / f'native/selected-{short}-primary-construction.json').read_text())
        group = 'controlled' if short.startswith('controlled_') else ('pedestrian' if short.startswith('pedestrian_') else 'concurrent')
        intervention = 'concurrent_indication' if group == 'concurrent' else 'ego_release_frame'
        cases.append({'case_id': construction['case_id'],
                      'target_law_id': template['law_id'], 'target_type': 'judgment_sweep',
                      'rationale': 'One-intervention requested source contrast; actual governance, lawful status and cautiousness remain unresolved.',
                      'variable_assignments': assignments(short),
                      'unresolved_judgment_calls': phrases,
                      'paired_probe_id': ROOT.name + '__' + group + '_comparison',
                      'deliberate_differences': [intervention],
                      'probe': {'primary_variable': intervention,
                                'comparison_or_standard': 'source-bound requested contrast without a legal cutoff',
                                'target_value_or_branch': short},
                      'recording_description': construction['recording_description']})
    specs = [{'sweep_id': 'pending-' + str(i), 'target_law_id': template['law_id'],
              'judgment_refs': [{'phrase': judgment['phrase'], 'note': judgment['note']}],
              'status': 'incomplete',
              'missing_inputs': ['Original Native physical feasibility and independent lawful-status/source review remain pending.'],
              'rationale': 'These selected branch contrasts do not define a physical judgment sweep or legal threshold.'}
             for i, judgment in enumerate(template['structure']['judgment_calls_needed'], 1)]
    proposal = {'cell_id': binding['cell_id'], 'actor': binding['actor'],
                'status': 'draft', 'cases': cases, 'sweep_specs': specs,
                'sweeps_expanded': True, 'original_native_observed': False}
    path = OUT / 'cases.json'
    path.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + '\n')
    index_path = OUT / 'semantic-index.json'
    index = json.loads(index_path.read_text())
    index['stages']['cases'] = {'path': 'proposals/cases.json', 'sha256': sha(path)}
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
