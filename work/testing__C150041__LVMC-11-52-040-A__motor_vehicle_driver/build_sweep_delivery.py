"""Materialize ten source-gated Native sweep bundles from the CPU diagnostic grid."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from parking_pose import SWEEP_REQUESTS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
TEMPLATE = 'park_angled_lawful'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def build():
    original = json.loads((ROOT / 'execution-manifest.json').read_text())
    template = next(row for row in original['cases']
                    if row['case_id'].endswith('__' + TEMPLATE))
    out = []
    for suffix in SWEEP_REQUESTS:
        folder = ROOT / 'diagnostic' / suffix
        exact = ROOT.name + '__' + suffix
        row = copy.deepcopy(template)
        for name, source_name in (('primary', 'construction.json'),
                                  ('fallback1', 'construction-fallback1.json')):
            package = json.loads((folder / source_name).read_text())
            package['files'] = [item for item in package['files']
                                if item['path'] != 'reviewed-context.json' and
                                not item['path'].startswith('reviewed_sources/')]
            for item in package['files']:
                if item['path'] == 'runner.py':
                    wrapper = json.loads((ROOT / 'diagnostic' / TEMPLATE / 'construction-delivery.json').read_text())
                    item['content'] = next(f['content'] for f in wrapper['files'] if f['path'] == 'runner.py').replace(TEMPLATE, suffix)
                elif item['path'] == 'tests/test_offline.py':
                    item['path'] = 'tests/test_delivery_offline.py'
                    item['source'] = str((ROOT / 'delivery_offline_test.py').relative_to(REPO))
                    item['content'] = (ROOT / 'delivery_offline_test.py').read_text()
            package['source_kind'] = 'worker_native_construction_pending_reviewed_site_packet'
            dest = folder / ('construction-delivery.json' if name == 'primary'
                             else 'construction-delivery-fallback1.json')
            write(dest, package)
            selected = row if name == 'primary' else row['candidates'][0]
            selected['construction'] = dest.relative_to(ROOT).as_posix()
            selected['construction_sha256'] = sha(dest)
            if name == 'fallback1':
                selected.pop('offline', None)
                selected.pop('compatibility', None)
        row['case_id'] = exact
        row['measurement_contract'] = f'diagnostic/{suffix}/measurement-contract.json'
        contract = json.loads((ROOT / 'diagnostic' / TEMPLATE / 'measurement-contract.json').read_text())
        contract['case_id'] = exact
        write(ROOT / row['measurement_contract'], contract)
        row['fixture_recipe'] = f'work/{ROOT.name}/diagnostic/{suffix}/saved-fixture-recipe.json'
        for key in ('offline', 'compatibility', 'negative', 'physical_preparation',
                    'delivery_acceptance', 'post_capture'):
            row.pop(key, None)
        row['preparation_status'] = 'source_gated_cpu_construction'
        out.append(row)
    draft = {'format': 'worker-execution-manifest', 'assignment_id': ROOT.name,
             'runtime_manifest_sha256': original['runtime_manifest_sha256'],
             'preparation_status': 'source_gated_cpu_construction',
             'cases': out}
    destination = ROOT / 'sweep-manifest-draft.json'
    write(destination, draft)
    return destination


if __name__ == '__main__':
    print(build())
