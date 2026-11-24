"""Replay pinned exact selected CPU validators without Native execution."""

import json
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')
if not OUTPUT or ROOT / '.runtime-work' not in Path(OUTPUT).resolve().parents:
    raise RuntimeError('Set physical SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
sys.path[:0] = [str(ROOT / 'runtime'), str(ROOT / 'runtime/scenario_pipeline')]

from scenario_pipeline.worker_exchange.execution_manifest import validate as execution
from scenario_pipeline.worker_exchange.semantic_delivery import validate as semantic
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case
from scenario_pipeline.worker_exchange.package_compatibility import check_receipts


def main():
    manifest = execution(ROOT, HERE.name)
    print('execution_manifest_pass', len(manifest['cases']), flush=True)
    original = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    print('semantic_pass', semantic(HERE, original, manifest), flush=True)
    for entry in manifest['cases']:
        validate_case(HERE, entry, original['selection_targets'])
    print('delivery_contract_pass', len(manifest['cases']), flush=True)
    check_receipts(ROOT, HERE, manifest)
    print('package_compatibility_pass', len(manifest['cases']), flush=True)


if __name__ == '__main__':
    main()
