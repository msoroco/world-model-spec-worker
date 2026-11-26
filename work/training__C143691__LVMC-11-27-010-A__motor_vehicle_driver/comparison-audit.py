"""Check controlled diagnostic comparison requests without claiming original outcomes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / 'case-plan.json').read_text())
VARIABLES = {
    'occupancy': None,
    'designation': 'official_designation',
    'dedication': 'city_dedication',
    'posting': 'appropriate_posting',
    'emergency': 'exception_kind',
    'maintenance': 'exception_kind',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rows = []
    for comparison in PLAN['comparisons']:
        name = comparison['comparison_id'].rsplit('__', 1)[-1]
        if name not in VARIABLES or len(comparison['case_ids']) != 2:
            raise ValueError('Unknown or unpaired comparison: ' + name)
        cases = comparison['case_ids']
        suffixes = [case.rsplit('__', 1)[-1] for case in cases]
        sources = [HERE / 'diagnostic-source' / suffix / 'trail-authority-context.json'
                   for suffix in suffixes]
        requests = [json.loads(path.read_text())['request'] for path in sources]
        changed = {key for key in requests[0] if requests[0][key] != requests[1][key]}
        expected = set() if name == 'occupancy' else {VARIABLES[name]}
        if changed != expected:
            raise ValueError('Controlled source request differs: ' + name)
        targets = [item for item in PLAN['cases'] if item['case_id'] in cases]
        if len(targets) != 2:
            raise ValueError('Comparison lacks exact cases: ' + name)
        rows.append({
            'comparison_id': comparison['comparison_id'],
            'case_ids': cases,
            'changed_request_keys': sorted(changed),
            'diagnostic_context_sha256': [sha(path) for path in sources],
            'source_originality': 'diagnostic_only',
            'original_native_outcome_reviewed': False,
        })
    if len(rows) != 6:
        raise ValueError('Full law comparison count differs')
    output = HERE / 'comparison-audit-specs.json'
    output.write_text(json.dumps({'format': 'c143691-comparison-audit-v1',
                                  'comparisons': rows,
                                  'all_original_reviews_pending': True}, indent=2) + '\n')
    print(json.dumps({'comparisons': len(rows), 'spec_sha256': sha(output)}))


if __name__ == '__main__':
    main()
