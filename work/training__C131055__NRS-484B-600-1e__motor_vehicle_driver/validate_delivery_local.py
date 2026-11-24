"""Validate both exact selected delivery CPU acceptance contracts locally."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
output = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
if not output.is_relative_to(ROOT / '.runtime-work'):
    raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first')
sys.path[:0] = [str(ROOT / 'runtime'), str(ROOT / 'runtime/scenario_pipeline')]
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        contract = validate_case(HERE, entry, expected_sets=['full-train'])
        print(entry['case_id'], 'delivery_contract_validated',
              contract['test_log_sha256'], contract['negative_log_sha256'])


if __name__ == '__main__':
    main()
