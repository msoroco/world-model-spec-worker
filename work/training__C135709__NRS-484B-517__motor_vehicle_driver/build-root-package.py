"""Materialize the first exact case as the portable root CPU bundle."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILES = ('runner.py', 'capture.py', 'check.py', 'prepare_raw.py',
         'measure_prepared.py', 'finalize_selected.py', 'triggers.py',
         'stand-road.xodr', 'requested-tracks.jsonl', 'assignment-source.json',
         'case-plan.json', 'measurement-contract.json', 'config.json')


def build():
    manifest = json.loads((ROOT/'execution-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__reference'))
    selected = json.loads((ROOT/entry['construction']).read_text())
    original = {item['path']: item['content'] for item in selected['files']}
    config = json.loads(original['config.json'])
    config['supported_case_ids'] = [e['case_id'] for e in manifest['cases']]
    original['config.json'] = json.dumps(config, indent=2)+'\n'
    construction = dict(selected)
    construction['files'] = [{'path': name, 'content': original[name]}
                             for name in FILES]
    construction['status'] = 'portable_root_first_exact_case_cpu_prepared'
    construction['delivery_ready'] = False
    for item in construction['files']:
        target = ROOT/item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and target.read_text() != item['content']:
            if target.name in ('case-plan.json', 'runner.py'):
                raise ValueError('Preserve authored root '+target.name)
        target.write_text(item['content'])
    (ROOT/'construction.json').write_text(json.dumps(construction, indent=2)+'\n')
    return construction


if __name__ == '__main__':
    print(json.dumps({'root_files': len(build()['files']),
                      'first_case_only': True}))
