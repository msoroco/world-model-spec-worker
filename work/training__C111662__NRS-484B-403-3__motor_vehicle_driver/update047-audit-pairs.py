"""Independently compare corrected-inventory saved CPU diagnostics."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from audit_saved_pair import CASES, audit  # noqa: E402

CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    pairs = []
    for branch, (left, right) in CASES.items():
        for candidate in CANDIDATES:
            l = HERE / 'update047-proof' / left / candidate / 'processing.json'
            r = HERE / 'update047-proof' / right / candidate / 'processing.json'
            result = audit(l, r, branch, candidate)
            if result['receipt_sha256'] != [sha(l), sha(r)]:
                raise ValueError('Pair audit receipt binding differs')
            pairs.append(result)
    output = HERE / 'update047-pair-audit.json'
    output.write_text(json.dumps({'format': 'c111662-inventory-v2-pair-audit-v1',
                                  'assignment_id': HERE.name, 'pair_count': len(pairs),
                                  'passed': len(pairs) == 8, 'pairs': pairs,
                                  'scope': 'synthetic saved pair comparison only'}, indent=2) + '\n')
    print(json.dumps({'pair_count': len(pairs), 'sha256': sha(output)}))


if __name__ == '__main__':
    main()
