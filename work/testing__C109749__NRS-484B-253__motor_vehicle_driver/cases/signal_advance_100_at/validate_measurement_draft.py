"""Validate the draft's case-specific source measurement and contract."""
import json
import sys
from pathlib import Path

folder = Path(__file__).resolve().parent
assignment = folder.parents[1]
repo = assignment.parent.parent
sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
sys.path.insert(0, str(assignment))
sys.path.insert(0, str(folder))

from worker_exchange.measurement_contract import validate
from finalizer import measure_signal_advance

case = json.loads((folder / 'config.json').read_text())['selected_case_id']
plan = json.loads((assignment / 'case-plan.json').read_text())
for row in plan['requirement_dispositions']:
    if row.get('status') == 'selected_required':
        row['case_ids'].append(case)
contract = json.loads((folder / 'measurement-contract.json').read_text())
validated = validate(contract, plan['requirement_dispositions'],
                     (folder / 'finalizer.py').read_text(), case)
assert {row['output_key'] for row in validated} == {
    'inside_yield_observation', 'signal_advance_observation',
    'reciprocal_yield_observation'}

root = repo / '.runtime-work/c109749-signal-distance-fixture-v2'
results = {}
for label, expected in (('25_0', False), ('30_48', True), ('36_0', True)):
    path = root / label / 'interaction_history.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    measured = measure_signal_advance(rows)
    probe = measured['probes']['30.48']
    assert probe['observable_distance_met'] is expected
    assert probe['full_signal_onset_observed'] is True
    results[label] = measured['observed_continuous_approach_distance_m']

rows = [json.loads(line) for line in
        (root / 'interrupted/interaction_history.jsonl').read_text().splitlines()
        if line]
assert not measure_signal_advance(rows)['probes']['30.48']['observable_distance_met']
print(json.dumps({'contract_validated': True, 'measured_m': results,
                  'interrupted_rejected': True, 'exact_compatibility_passed': False,
                  'physical_acceptance_claimed': False}, sort_keys=True))
