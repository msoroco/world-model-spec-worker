"""Run pinned selected package validators without changing truthful status."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output_root = os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')
    if not output_root or not Path(output_root).resolve().is_relative_to(REPO / '.runtime-work'):
        raise ValueError('pipeline output root must be under .runtime-work')
    sys.path[:0] = [str(REPO / 'runtime/scenario_pipeline'), str(REPO / 'runtime/python')]
    from worker_exchange.execution_manifest import validate as execution
    from worker_exchange.semantic_delivery import validate as semantic
    from worker_exchange.package_compatibility import check_receipts
    from worker_exchange.physical_preparation import validate as physical
    from worker_exchange.delivery_handoff import validate_case as delivery

    manifest = execution(REPO, HERE.name)
    assignment = json.loads((REPO / 'inputs' / HERE.name / 'assignment.json').read_text())
    semantic_result = semantic(HERE, assignment, manifest)
    if check_receipts(REPO, HERE, manifest) is not True:
        raise ValueError('selected compatibility receipts failed')
    cases = []
    for entry in manifest['cases']:
        physical(REPO, HERE, entry)
        delivery(HERE, entry, assignment.get('selection_targets'))
        cases.append(entry['case_id'])
    result = {'format': 'c143687-selected-validator-report-v1',
              'assignment_id': HERE.name,
              'manifest_sha256': sha(HERE / 'execution-manifest.json'),
              'selected_execution': 'passed', 'semantic': 'passed',
              'compatibility': 'passed', 'physical': 'passed',
              'delivery': 'passed', 'semantic_result': semantic_result,
              'cases': cases, 'original_delivery_claimed': False}
    (HERE / 'selected-validator-report.json').write_text(
        json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('five selected pinned validators passed for three source-gated cases')


if __name__ == '__main__':
    main()
