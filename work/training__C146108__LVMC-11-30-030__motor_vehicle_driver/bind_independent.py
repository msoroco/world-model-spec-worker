"""Hash independent delivery and comparison positive/negative CPU predicates."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SLUGS = ('false', 'true', 'unmarked_false', 'unmarked_true')
COMPARISONS = ('marked_pass_contrast', 'unmarked_intersection_pass_contrast',
               'false_crosswalk_kind_contrast', 'true_crosswalk_kind_contrast')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def item(kind, key, negative):
    name = f'{kind}-{key}-' + ('negative' if negative else 'positive') + '.log'
    path = HERE / name
    output = path.read_text()
    expected = 'Original frame or camera join differs' if kind == 'comparison' else 'Exact original Native result missing'
    if negative and expected not in output:
        raise ValueError('Negative independent predicate absent: ' + name)
    if not negative and 'cpu_predicates_passed' not in output:
        raise ValueError('Positive independent predicate absent: ' + name)
    value = AID + '__' + key
    cmd = f'.venv-cpu/bin/python -B work/{AID}/{kind}_audit.py --' + ('comparison' if kind == 'comparison' else 'case') + ' ' + value + ' --self-test'
    if negative:
        cmd += ' --negative'
    return {'command': cmd, 'exit_code': 1 if negative else 0, 'log': name,
            'log_sha256': sha(path), **({'negative_expected_error': expected} if negative else {})}


def main():
    value = {'format': 'worker-crosswalk-independent-audit-cpu',
             'diagnostic_only': True, 'original_acquisition_claimed': False,
             'delivery': {slug: {'positive': item('delivery', slug, False),
                                  'negative': item('delivery', slug, True)} for slug in SLUGS},
             'comparisons': {AID + '__' + name: {
                 'positive': item('comparison', name, False),
                 'negative': item('comparison', name, True)} for name in COMPARISONS}}
    path = HERE / 'independent-audit-proof.json'
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'delivery': len(SLUGS), 'comparisons': len(COMPARISONS),
                      'sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
