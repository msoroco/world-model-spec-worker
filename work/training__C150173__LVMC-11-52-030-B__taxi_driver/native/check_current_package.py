"""Validate current-runtime selected taxi bindings without asserting readiness."""
import json
from pathlib import Path
import sys


PACKAGE = Path(__file__).resolve().parent.parent
ROOT = PACKAGE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.delivery_handoff import validate_case  # noqa: E402
from worker_exchange.execution_manifest import validate as execution  # noqa: E402
from worker_exchange.package_compatibility import check_receipts  # noqa: E402
from worker_exchange.semantic_delivery import validate as semantic  # noqa: E402


def check():
    assignment = json.loads((ROOT / 'inputs' / PACKAGE.name / 'assignment.json').read_text())
    manifest = execution(ROOT, PACKAGE.name)
    stages = semantic(PACKAGE, assignment, manifest)
    for entry in manifest['cases']:
        validate_case(PACKAGE, entry, assignment['selection_targets'])
    compatibility = check_receipts(ROOT, PACKAGE, manifest)
    construction = json.loads((PACKAGE / 'construction.json').read_text())
    if construction['entrypoint'] != 'runner.py':
        raise ValueError('Canonical taxi root runner missing')
    for item in construction['files']:
        if (PACKAGE / item['path']).read_text() != item['content']:
            raise ValueError('Canonical taxi root implementation differs: ' + item['path'])
    config = json.loads((PACKAGE / 'config.json').read_text())
    planned = {item['case_id'] for item in manifest['cases']}
    if set(config['supported_case_ids']) != planned:
        raise ValueError('Canonical taxi root config omits a selected case')
    return {'exact_cases': len(planned), 'semantic_stages': stages['stage_count'],
            'delivery_contracts': len(manifest['cases']),
            'compatibility_receipts': compatibility,
            'canonical_root_files': len(construction['files']),
            'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
