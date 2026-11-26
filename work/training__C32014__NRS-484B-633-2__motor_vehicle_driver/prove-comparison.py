"""Source-shaped CPU positives and negatives for bridge comparison audit."""
import json
from pathlib import Path
import shutil

from bridge_comparison_audit import audit

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / '.runtime-work/c32014-measure-fixtures'
BELOW = FIXTURES / 'below'
ABOVE = FIXTURES / 'above'
NEGATIVE = ROOT / '.runtime-work/c32014-comparison-negative'


def reject(below, above, expected):
    try:
        audit(below, above)
    except ValueError as error:
        assert expected in str(error), str(error)
        return str(error)
    raise AssertionError('independent comparison accepted missing or changed source')


def main():
    positive = audit(BELOW, ABOVE)
    assert positive['passed'] and not positive['physical_acceptance_claimed']
    NEGATIVE.mkdir(parents=True, exist_ok=True)
    copied = NEGATIVE / 'above'
    copied.mkdir(exist_ok=True)
    shutil.copyfile(ABOVE / 'bridge-speed-history.jsonl', copied / 'bridge-speed-history.jsonl')
    context = json.loads((ABOVE / 'bridge-context.json').read_text())
    context['sign_limit_mph'] = 30.0
    (copied / 'bridge-context.json').write_text(json.dumps(context) + '\n')
    changed_sign = reject(BELOW, copied, 'structural boundary or sign value missing')
    (copied / 'bridge-context.json').write_text((ABOVE / 'bridge-context.json').read_text())
    missing = copied / 'bridge-speed-history.jsonl'
    missing.unlink()
    try:
        audit(BELOW, copied)
    except FileNotFoundError:
        missing_source = 'missing original history rejected'
    else:
        raise AssertionError('missing original history accepted')
    reversed_pair = reject(ABOVE, BELOW, 'below-posting attempt exceeded')
    print(json.dumps({'passed': True, 'source_kind': 'synthetic_native_sample',
                      'negative_changed_sign': changed_sign,
                      'negative_missing_source': missing_source,
                      'negative_reversed_pair': reversed_pair,
                      'department_determination_verified': False}, sort_keys=True))


if __name__ == '__main__':
    main()
