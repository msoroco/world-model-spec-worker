"""Read-only source and status audit for frozen full-train partition 08."""
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ids = json.loads((ROOT / 'partitions/full-train-08.json').read_text())['assignment_ids']
counts = Counter()
errors = []
for assignment in ids:
    source_path = ROOT / 'inputs' / assignment / 'assignment.json'
    source = json.loads(source_path.read_text())
    plan = json.loads((ROOT / 'work' / assignment / 'case-plan.json').read_text())
    result = json.loads((ROOT / 'work' / assignment / 'result.json').read_text())
    counts['assignments'] += 1
    counts[result['status']] += 1
    counts['planned_cases'] += len(plan['cases'])
    counts['comparisons'] += len(plan['comparisons'])
    counts['frozen_witness_branches'] += len(source['branches'])
    counts['dispositions'] += len(plan.get('requirement_dispositions', []))
    counts['selected_delivery_cases'] += sum(case['kind'] == 'delivery' for case in plan['cases'])
    counts['candidate_plans'] += len(plan.get('candidate_plans', []))
    if hashlib.sha256(source_path.read_bytes()).hexdigest() != result['input_sha256']:
        errors.append([assignment, 'input hash mismatch'])
    if source['law_record']['text'] != plan['source_law']['text']:
        errors.append([assignment, 'frozen law text mismatch'])
    if len(plan['cases']) != result['planned_case_count']:
        errors.append([assignment, 'planned case count mismatch'])
    if len(plan['comparisons']) != result['comparison_count']:
        errors.append([assignment, 'comparison count mismatch'])

assert len(ids) == 31
assert not errors, errors
print(json.dumps({'partition': 'full-train-08', 'counts': dict(sorted(counts.items())), 'mismatches': errors}, indent=2))
