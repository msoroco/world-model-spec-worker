"""Materialize the six-case index required by package acceptance."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('probe_a', 'probe_b', 'curve_right', 'curve_left',
         'one_way_crest', 'one_way_curve')


def main():
    first = json.loads((HERE / 'selected-constructions/probe_a/primary/construction.json').read_text())
    config_part = next(part for part in first['files'] if part['path'] == 'config.json')
    config = json.loads(config_part['content'])
    config['supported_case_ids'] = [HERE.name + '__' + suffix for suffix in CASES]
    config_part['content'] = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
    runner = next(part for part in first['files'] if part['path'] == 'runner.py')
    runner['content'] = (HERE / 'root_runner.py').read_text()
    runner['source'] = 'work/' + HERE.name + '/root_runner.py'
    test = next(part for part in first['files'] if part['path'] == 'tests/test_selected.py')
    test['path'] = 'tests/test_root.py'
    test['content'] = (HERE / 'root_test.py').read_text()
    test['source'] = 'work/' + HERE.name + '/root_test.py'
    first['static_checks'] = ['six exact selected case identities',
                              'current source bindings',
                              'no original Native or legal acceptance claimed']
    first['status'] = 'six_case_delivery_index_cpu_prepared'
    for part in first['files']:
        target = HERE / part['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(part['content'])
    target = HERE / 'construction.json'
    target.write_text(json.dumps(first, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'root_construction_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                      'case_count': len(config['supported_case_ids'])}))


if __name__ == '__main__':
    main()
