"""Independently check every selected fallback proof and damaged-binding rejection."""
import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'runtime/pipeline'))
from scenario_pipeline.worker_exchange.candidate_constructions import validate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE/'execution-manifest.json').read_text())
    plan = json.loads((HERE/'case-plan.json').read_text())
    expected = {row['case_id'] for row in plan['cases']}
    if (manifest['format'] != 'worker-execution-manifest' or
            {row['case_id'] for row in manifest['cases']} != expected or
            len(manifest['cases']) != 2):
        raise ValueError('Selected manifest exact cases differ')
    reviewed = []
    rejected = []
    for entry in manifest['cases']:
        if entry['kind'] != 'delivery':
            raise ValueError('Expected selected delivery construction')
        result = validate(HERE, entry, plan['law_id'], plan['cell_id'],
                          required=True, require_alternate=True, candidate_count=4)
        if result['fallbacks'] != ['fallback1', 'fallback2', 'fallback3']:
            raise ValueError('Selected fallback set differs')
        reviewed.append(entry['case_id'])
        for label, edit in (
                ('construction_hash', lambda x: x['candidates'][0].update(construction_sha256='0'*64)),
                ('offline_hash', lambda x: x['candidates'][0]['offline'].update(log_sha256='0'*64)),
                ('compatibility_hash', lambda x: x['candidates'][0]['compatibility'].update(sha256='0'*64))):
            damaged = copy.deepcopy(entry)
            edit(damaged)
            try:
                validate(HERE, damaged, plan['law_id'], plan['cell_id'],
                         required=True, require_alternate=True, candidate_count=4)
            except ValueError:
                rejected.append(entry['case_id']+':'+label)
            else:
                raise ValueError('Damaged selected binding was accepted: '+label)
    report = {'format': 'c10014-selected-candidate-binding-audit',
              'manifest_sha256': sha(HERE/'execution-manifest.json'),
              'selected_cases': reviewed, 'candidate_plans_proven': 8,
              'rejected_mutations': rejected,
              'scope': 'selected offline/compatibility bindings only; physical proof pending'}
    (HERE/'selected-binding-audit.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'passed': True, 'cases': len(reviewed),
                      'candidate_plans': 8, 'rejected_mutations': len(rejected)}))


if __name__ == '__main__':
    main()
