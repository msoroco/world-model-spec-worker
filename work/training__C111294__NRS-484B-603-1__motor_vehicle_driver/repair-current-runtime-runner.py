"""Rebind selected C111294 runner imports to the active runtime tree.

All changed constructions require fresh exact offline/public/saved proof receipts.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = ('runtime/pipeline/scenario_pipeline', 'runtime/pipeline/python')
NEW = ('runtime/scenario_pipeline', 'runtime/python')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def revise(text):
    for old, new in zip(OLD, NEW):
        text = text.replace(old, new)
    return text


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    folders = [HERE / f'current-v2-{case}-{candidate}-diagnostic'
               for case in ('probe_a', 'probe_b') for candidate in ('fallback1',)]
    folders += [HERE / f'current-v2-{case}-diagnostic' for case in ('probe_a', 'probe_b')]
    folders += [p for branch in ('weather', 'pedestrian', 'obstruction')
                for p in sorted((HERE / (branch + '-branch-drafts')).iterdir())
                if p.is_dir() and (p / 'construction.json').is_file()]
    folders.append(HERE)
    changed = []
    for folder in folders:
        path = folder / 'construction.json'
        construction = json.loads(path.read_text())
        runners = [row for row in construction['files'] if row['path'] == 'runner.py']
        if len(runners) != 1:
            raise ValueError('Exact runner missing: ' + str(path))
        before = runners[0]['content']
        after = revise(before)
        if after == before:
            continue
        runners[0]['content'] = after
        write_json(path, construction)
        materialized = folder / 'runner.py'
        if materialized.is_file():
            materialized.write_text(after)
        changed.append(str(path.relative_to(HERE)))
    manifests = list(HERE.glob('current-v2-*-diagnostic-manifest.json'))
    manifests += list(HERE.glob('weather_*-diagnostic-manifest.json'))
    manifests += list(HERE.glob('pedestrian_*-diagnostic-manifest.json'))
    manifests += list(HERE.glob('obstruction_*-diagnostic-manifest.json'))
    for path in manifests:
        manifest = json.loads(path.read_text())
        for entry in manifest['cases']:
            entry['construction_sha256'] = sha(HERE / entry['construction'])
            for candidate in entry.get('candidates', []):
                candidate['construction_sha256'] = sha(HERE / candidate['construction'])
        write_json(path, manifest)
    print(json.dumps({'changed_constructions': changed,
                      'updated_diagnostic_manifests': len(manifests)}))


if __name__ == '__main__':
    main()
