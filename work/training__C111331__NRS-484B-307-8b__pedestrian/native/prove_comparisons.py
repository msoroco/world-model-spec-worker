"""Run each exact comparison and reject a missing original source."""

import hashlib
import json
import os
from pathlib import Path
import sys

folder = Path(__file__).resolve().parent.parent
repo = folder.parents[1]
scratch = repo / '.runtime-work/c111331-comparison-negative'
sys.path.insert(0, str(folder))
from comparison_audit import audit


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def positive_path(cid):
    condition = cid.rsplit('__', 1)[-1]
    return (repo / '.runtime-work/c111331-compat-a-primary-v5' if condition == 'condition_a'
            else repo / f'.runtime-work/c111331-compat-{condition}-primary-v5')


def main():
    if os.environ.get('PYTHONDONTWRITEBYTECODE') != '1':
        raise ValueError('Disable bytecode in work tree')
    plan = json.loads((folder / 'case-plan.json').read_text())
    for item in plan['comparisons']:
        name = item['comparison_id'].split('__')[-1]
        left, right = (positive_path(cid) for cid in item['case_ids'])
        result = audit(item['comparison_id'], left, right)
        output = folder / ('comparison-' + name + '.json')
        output.write_text(json.dumps(result, indent=2) + '\n')
        negative = scratch / name
        negative.mkdir(parents=True, exist_ok=True)
        for path in right.iterdir():
            if path.name != 'red-entry-original.jsonl':
                target = negative / path.name
                if not target.exists():
                    target.symlink_to(path.resolve(), target_is_directory=path.is_dir())
        try:
            audit(item['comparison_id'], left, negative)
        except ValueError as error:
            if 'Missing required source: red-entry-original.jsonl' not in str(error):
                raise
            negative_message = str(error)
        else:
            raise ValueError('Missing comparison source was accepted')
        log = folder / ('comparison-' + name + '-negative.log')
        log.write_text(negative_message + '\n')
        print(json.dumps({'comparison_id': item['comparison_id'],
                          'positive_sha256': sha(output),
                          'negative_log_sha256': sha(log)}))


if __name__ == '__main__':
    main()
