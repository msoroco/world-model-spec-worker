"""Check each exact draft's canonical semantic recording contract."""

import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def validate():
    output = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    scratch = (ROOT / '.runtime-work').resolve()
    if output != scratch and scratch not in output.parents:
        raise ValueError('Runtime output root must be under .runtime-work')
    sys.path.insert(0, str(ROOT / 'runtime' / 'scenario_pipeline'))
    from batch_pipeline.validation import recording_description

    results = []
    for suffix in ('probe_a', 'probe_b', 'probe_c', 'probe_d'):
        path = HERE / (suffix + '-construction.json')
        construction = json.loads(path.read_text())
        recording_description(construction['recording_description'])
        results.append({
            'case_id': construction['case_id'],
            'construction_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'recording_description_valid': True,
        })
    return {'format': 'c183370-recording-description-proof',
            'scope': 'semantic schema only; no original physical observations',
            'cases': results}


if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
