"""Exercise the current canonical semantic validator on this exact package."""
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
from scenario_pipeline.worker_exchange.semantic_delivery import validate


def main():
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    print(json.dumps(validate(HERE, assignment, manifest), sort_keys=True))


if __name__ == '__main__':
    main()
