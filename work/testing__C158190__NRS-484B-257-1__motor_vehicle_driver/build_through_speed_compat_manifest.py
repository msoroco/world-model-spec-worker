"""Bind source recipes to exact unselected speed constructions for CPU replay."""

import copy
import hashlib
import json
from pathlib import Path

from through_speed_sweep import TARGETS_MPS

ROOT = Path(__file__).resolve().parent


def main():
    selected = json.loads((ROOT / 'execution-manifest.json').read_text())
    template = selected['cases'][0]
    entries = []
    for target in TARGETS_MPS:
        speed = int(target)
        path = ROOT / f'cases/through_speed_{speed}/construction.json'
        recipe = ROOT / f'cases/through_speed_{speed}/diagnostic-recipe.json'
        if not recipe.is_file():
            raise ValueError(f'Missing target-specific speed-{speed} source recipe')
        entry = copy.deepcopy(template)
        for key in ('candidates', 'negative', 'offline', 'compatibility',
                    'delivery_acceptance', 'physical_preparation'):
            entry.pop(key, None)
        entry.update(case_id=ROOT.name + f'__yield_nearest_view_through_speed_{speed}',
                     kind='diagnostic_unselected',
                     construction=str(path.relative_to(ROOT)),
                     construction_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                     fixture_recipe=str(recipe.relative_to(ROOT.parents[1])),
                     candidate_risk={'status': 'physical',
                                     'reason': 'through motion, sight and pixels need original Native verification'})
        entries.append(entry)
    manifest = {key: selected[key] for key in ('format', 'assignment_id',
                                                'runtime_manifest_sha256')}
    manifest['cases'] = entries
    path = ROOT / 'through-speed-compatibility-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(entries), 'source_recipes': len(entries)}))


if __name__ == '__main__':
    main()
