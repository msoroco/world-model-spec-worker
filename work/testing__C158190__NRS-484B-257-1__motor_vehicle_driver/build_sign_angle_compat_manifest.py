"""Bind unselected sign-angle exact constructions to original-source recipes."""

import copy
import hashlib
import json
from pathlib import Path

from build_sign_angle_cases import ANGLES_RAD

ROOT = Path(__file__).resolve().parent


def main():
    selected = json.loads((ROOT / 'execution-manifest.json').read_text())
    template = selected['cases'][0]
    cases = []
    for angle, label in ANGLES_RAD:
        construction = ROOT / f'cases/sign_angle_{label}/construction.json'
        recipe = ROOT / f'cases/sign_angle_{label}/diagnostic-recipe.json'
        if not recipe.is_file():
            raise ValueError('Sign-angle source recipe missing: ' + label)
        entry = copy.deepcopy(template)
        for key in ('candidates', 'negative', 'offline', 'compatibility',
                    'delivery_acceptance', 'physical_preparation'):
            entry.pop(key, None)
        entry.update(case_id=ROOT.name + '__yield_nearest_view_sign_angle_' + label,
                     kind='diagnostic_unselected',
                     construction=str(construction.relative_to(ROOT)),
                     construction_sha256=hashlib.sha256(construction.read_bytes()).hexdigest(),
                     fixture_recipe=str(recipe.relative_to(ROOT.parents[1])),
                     candidate_risk={'status': 'physical',
                                     'reason': 'Native sign orientation and original sign-face pixels need verification'},
                     authored_sign_hOffset_rad=angle)
        cases.append(entry)
    manifest = {key: selected[key] for key in
                ('format', 'assignment_id', 'runtime_manifest_sha256')}
    manifest['cases'] = cases
    path = ROOT / 'sign-angle-compatibility-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'source_recipes': len(cases)}))


if __name__ == '__main__':
    main()
