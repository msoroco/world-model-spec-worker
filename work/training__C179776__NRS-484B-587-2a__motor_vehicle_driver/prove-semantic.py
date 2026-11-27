"""Validate this assignment's six canonical semantic stage outputs."""

import json
import os
from pathlib import Path
import sys


def main():
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if repo / '.runtime-work' not in output_root.parents:
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    sys.path.insert(0, str(repo / 'runtime' / 'scenario_pipeline'))
    from worker_exchange.semantic_delivery import validate
    original = json.loads((repo / 'inputs' / folder.name / 'assignment.json').read_text())
    manifest = json.loads((folder / 'execution-manifest.json').read_text())
    print(json.dumps(validate(folder, original, manifest), sort_keys=True))


if __name__ == '__main__':
    main()
