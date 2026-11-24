"""Independently check the two selected synthetic right-turn contrasts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text())

manifest = read(HERE / 'execution-manifest.json')
assert len(manifest['cases']) == 2
samples = []
results = []
for index, entry in enumerate(manifest['cases'], 1):
    assert entry['case_id'] == HERE.name + f'__controlled_{index}'
    construction = HERE / entry['construction']
    assert sha(construction) == entry['construction_sha256']
    recipe = ROOT / entry['fixture_recipe']
    spec = read(recipe)
    generator = ROOT / spec['generator']['source']
    assert sha(generator) == spec['generator']['sha256']
    files = read(generator)['files']
    source = [json.loads(line) for line in files['native_samples.jsonl'].splitlines()]
    assert len(source) == 600
    samples.append(source)
    result_path = HERE / f'selected-{index}-primary-result.json'
    assert sha(result_path) == entry['saved_processing']['result_sha256']
    result = read(result_path)
    assert result['case_id'] == entry['case_id']
    assert result['provenance_kind'] == 'synthetic_local_diagnostic'
    assert result['accepted'] is False and result['legal_verdict_claimed'] is False
    assert result['target_checks'][0]['matched'] is True
    results.append(result)
    saved = HERE / entry['saved_processing']['receipt']
    assert sha(saved) == entry['saved_processing']['sha256']
    assert read(saved)['originals_preserved'] is True
fixed = ('signal_state_observed', 'turn_prohibition_present',
         'walker_conflict_occupied', 'cross_traffic_conflict_occupied')
for before, after in zip(*samples):
    assert all(before[key] == after[key] for key in fixed)
assert read(HERE / manifest['cases'][0]['construction'])['recording_description'] == \
       read(HERE / manifest['cases'][1]['construction'])['recording_description']
observed = [result['measured_values']['turn_yield'] for result in results]
assert observed[0]['yielded_to_lawful_users'] is True
assert observed[1]['yielded_to_lawful_users'] is False
assert observed[0]['sampled_clearance_s'] == 1.05
assert observed[1]['sampled_clearance_s'] == -0.75
print(json.dumps({'format': 'worker-right-turn-selected-comparison-cpu',
                  'case_ids': [entry['case_id'] for entry in manifest['cases']],
                  'construction_sha256': [entry['construction_sha256'] for entry in manifest['cases']],
                  'sampled_clearance_s': [row['sampled_clearance_s'] for row in observed],
                  'fixed_source_fields': fixed, 'frames': 600,
                  'synthetic_diagnostic': True, 'physical_or_legal_acceptance': False}, indent=2))
