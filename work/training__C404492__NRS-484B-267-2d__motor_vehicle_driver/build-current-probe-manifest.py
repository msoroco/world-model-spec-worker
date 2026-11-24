"""Bind exact draft constructions to public compatibility diagnostic recipes."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    draft = json.loads((HERE / 'draft-emergency-manifest.json').read_text())
    batch = json.loads((ROOT / 'batch.json').read_text())
    entries = []
    for source in draft['cases']:
        suffix = source['case_id'].rsplit('__', 1)[-1]
        entry = {key: source[key] for key in ('case_id', 'construction',
                 'construction_sha256', 'measurement_contract',
                 'measurement_procedure', 'candidate_risk', 'candidates')}
        entry['id'] = 'primary'
        entry['kind'] = 'delivery'
        entry['fixture_recipe'] = (HERE / f'current-{suffix}-recipe.json').relative_to(ROOT).as_posix()
        entries.append(entry)
    target = HERE / 'current-probe-manifest.json'
    target.write_text(json.dumps({'format': 'worker-execution-manifest',
        'assignment_id': HERE.name, 'status': 'partial', 'delivery_ready': False,
        'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
        'cases': entries}, indent=2) + '\n')
    print(json.dumps({'cases': len(entries), 'manifest': target.name}))


if __name__ == '__main__':
    main()
