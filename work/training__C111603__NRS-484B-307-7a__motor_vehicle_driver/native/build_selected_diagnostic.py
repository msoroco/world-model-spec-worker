"""Adapt retained source-shaped diagnostics to current Core speed decoding."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    manifest = json.loads((ROOT / 'selected-compatibility-manifest.json').read_text())
    for case, source in (('controlled_1', 'primary'), ('controlled_2', 'contrast')):
        original = ROOT / f'current-v2-{source}-sources'
        selected = ROOT / f'selected-source-{case}'
        selected.mkdir(exist_ok=True)
        for item in original.rglob('*'):
            if item.is_file():
                destination = selected / item.relative_to(original)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(item, destination)
        trace = selected / 'trace.jsonl'
        rows = [json.loads(line) for line in trace.read_text().splitlines()]
        for index, row in enumerate(rows):
            if row.get('frame') != index or row.get('speed_mps') is None:
                raise ValueError('Retained source speed/frame inventory differs')
            before = rows[max(index - 1, 0)]['position_m']
            after = rows[min(index + 1, len(rows) - 1)]['position_m']
            interval = 0.05 if index in (0, len(rows) - 1) else 0.10
            # Differencing synthetic requested positions supplies only a CPU
            # fixture velocity, never an original Native velocity measurement.
            row['velocity_mps'] = [(after[0] - before[0]) / interval,
                                   (after[1] - before[1]) / interval, 0.0]
        trace.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
        source_manifest = selected / 'capture/manifest.json'
        declared = json.loads(source_manifest.read_text())
        declared['sources']['trace.jsonl'] = sha(trace)
        dump(source_manifest, declared)
        sources = []
        for item in sorted(selected.rglob('*')):
            if item.is_file():
                sources.append({'path': str(item.relative_to(selected)),
                                'source': str(item.relative_to(REPO)),
                                'sha256': sha(item)})
        spec = ROOT / f'current-v2-{source}-fixture-spec.json'
        recipe = ROOT / f'selected-{case}-fixture-recipe.json'
        dump(recipe, {'format': 'worker-fixture-recipe', 'sources': sources,
                      'generator': {'source': str(spec.relative_to(REPO)),
                                    'sha256': sha(spec)}})
        entry = next(x for x in manifest['cases'] if x['case_id'].endswith('__' + case))
        entry['fixture_recipe'] = str(recipe.relative_to(REPO))
    dump(ROOT / 'selected-compatibility-manifest.json', manifest)


if __name__ == '__main__':
    build()
