"""Run every assignment-local pinned contract and all 32 offline dispatches."""

import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.execution_manifest import validate as validate_execution
from worker_exchange.semantic_delivery import validate as validate_semantic
from worker_exchange.delivery_handoff import validate_case
from worker_exchange.package_compatibility import check_receipts
from worker_exchange.branch_coverage import validate_evidence


def main():
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    manifest = validate_execution(ROOT, HERE.name)
    semantic = validate_semantic(HERE, assignment, manifest)
    check_receipts(ROOT, HERE, manifest)
    validate_evidence(ROOT, HERE.name, json.loads((HERE / 'case-plan.json').read_text()))
    for entry in manifest['cases']:
        validate_case(HERE, entry, assignment['selection_targets'])
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            subprocess.run([sys.executable, str(HERE / 'runner.py'),
                            '--case', entry['case_id'], '--candidate', candidate, '--check'],
                           cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    print(json.dumps({'assignment_id': HERE.name, 'exact_cases': len(manifest['cases']),
                      'offline_dispatches': 4 * len(manifest['cases']),
                      'semantic': semantic, 'physical_and_delivery_receipts': 'passed',
                      'source_compatibility': 'passed', 'accepted_evidence_review': 'passed'}, indent=2))


if __name__ == '__main__':
    main()
