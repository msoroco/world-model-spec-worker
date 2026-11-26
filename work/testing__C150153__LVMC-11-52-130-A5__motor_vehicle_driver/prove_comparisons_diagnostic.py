"""Exercise ten frozen synthetic comparison pairs and sealed-source rejection."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from comparison_audit import compare

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / '.runtime-work/c150153-owner'
REPLAYED = {'front_park', 'front_stop', 'front_stand', 'west_inside'}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attempt(case_id: str) -> Path:
    kind = case_id.removeprefix(HERE.name + '__')
    suffix = '-bound' if kind in REPLAYED else ''
    return BASE / ('saved-source-' + kind.replace('_', '-') + suffix)


def prove() -> None:
    manifest = HERE / 'execution-manifest.source-bound-diagnostic.json'
    if json.loads(manifest.read_text())['status'] != 'synthetic_diagnostic_only_unselected_original_capture_pending':
        raise ValueError('Original production manifest cannot use diagnostic comparisons')
    plan = json.loads((HERE / 'case-plan.json').read_text())
    rows = []
    for spec in plan['comparisons']:
        comparison_id = spec['comparison_id']
        left, right = map(attempt, spec['case_ids'])
        packet = left / 'reviewed-site/packet.json'
        sources = left / 'reviewed-site/sources'
        positive = compare(comparison_id, left, right, packet, sources,
                           diagnostic_fixture=True, decoder=lambda *_: 900)
        if (positive['comparison_id'] != comparison_id or
                positive['case_ids'] != spec['case_ids'] or
                positive['fixed_conditions_checked'] != spec['fixed_conditions'] or
                positive['physical_acceptance_claimed'] is not False or
                positive['legal_judgment'] is not None):
            raise ValueError('Incomplete synthetic comparison: ' + comparison_id)
        with TemporaryDirectory(dir=BASE, prefix='comparison-negative-') as temp:
            changed = Path(temp) / 'attempt'
            shutil.copytree(right, changed, copy_function=os.link)
            (changed / 'comparison-context.json').unlink()
            try:
                compare(comparison_id, left, changed, packet, sources,
                        diagnostic_fixture=True, decoder=lambda *_: 900)
            except ValueError as error:
                negative = str(error)
                if 'comparison-context.json' not in negative:
                    raise ValueError('Wrong comparison source rejection: ' + negative) from error
            else:
                raise ValueError('Missing comparison source passed: ' + comparison_id)
        receipt = {'format': 'c150153-diagnostic-comparison',
                   'comparison_id': comparison_id,
                   'manifest_sha256': sha(manifest),
                   'left_capture_seal_sha256': sha(left / 'capture-seal.json'),
                   'right_capture_seal_sha256': sha(right / 'capture-seal.json'),
                   'positive': positive,
                   'negative_missing': 'comparison-context.json',
                   'negative_error': negative,
                   'scope': 'synthetic protocol only',
                   'physical_acceptance_claimed': False}
        path = HERE / ('cpu-comparison-' + comparison_id + '.json')
        path.write_text(json.dumps(receipt, indent=2) + '\n')
        rows.append({'comparison_id': comparison_id, 'receipt': path.name,
                     'sha256': sha(path)})
        print(comparison_id, 'fixed conditions and missing source passed', flush=True)
    index = {'format': 'c150153-diagnostic-comparison-index',
             'status': 'synthetic_diagnostic_only',
             'manifest_sha256': sha(manifest), 'comparisons': rows}
    (HERE / 'diagnostic-comparison-index.json').write_text(json.dumps(index, indent=2) + '\n')


if __name__ == '__main__':
    prove()
