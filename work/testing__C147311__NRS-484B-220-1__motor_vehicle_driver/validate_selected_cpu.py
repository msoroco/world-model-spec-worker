"""Direct pinned selected validators for source-gated one-way preparation."""
from __future__ import annotations

import json
from pathlib import Path

import scenario_pipeline.worker_exchange.execution_manifest as execution
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case
from scenario_pipeline.worker_exchange.package_compatibility import check_receipts
from scenario_pipeline.worker_exchange.physical_preparation import validate as physical
from scenario_pipeline.worker_exchange.semantic_delivery import validate as semantic


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def checked(fn):
    try:
        value = fn()
        return {'passed': True, 'result': value}
    except Exception as error:
        return {'passed': False, 'error_type': type(error).__name__, 'error': str(error)}


def run():
    assignment = json.loads((REPO / 'inputs' / HERE.name / 'assignment.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    outcomes = {
        'selected_execution': checked(lambda: execution.validate(REPO, HERE.name)),
        'semantic': checked(lambda: semantic(HERE, assignment, manifest)),
        'compatibility': checked(lambda: check_receipts(REPO, HERE, manifest)),
        'physical': checked(lambda: [physical(REPO, HERE, entry) for entry in manifest['cases']]),
        'delivery': checked(lambda: [validate_case(HERE, entry, assignment['selection_targets'])
                                     for entry in manifest['cases']]),
    }
    report = {'format': 'c147311-selected-cpu-validator-report-v1',
              'assignment_id': HERE.name, 'status': 'partial',
              'outcomes': outcomes, 'original_source_acceptance_claimed': False}
    (HERE / 'selected-validator-report.json').write_text(
        json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, sort_keys=True))
