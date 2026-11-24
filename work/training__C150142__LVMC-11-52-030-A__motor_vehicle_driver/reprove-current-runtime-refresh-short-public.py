"""Run the existing short public proof driver against the refreshed runtime.

Fresh paths prevent historical receipts from being counted as current proofs.
"""

import argparse
import json
from pathlib import Path
import runpy


WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
BASE = WORK / 'reprove-current-runner-short-public.py'
SOURCE = WORK / 'current-runtime-refresh-short-draft-manifest.json'
SCRATCH = REPO / '.runtime-work/owner150142/runtime-refresh-short-public'
PORTABLE = WORK / 'current-runtime-refresh-short-public'
INDEX = WORK / 'current-runtime-refresh-short-public-index.json'


def run(limit):
    source = json.loads(SOURCE.read_text())
    current = __import__('hashlib').sha256(
        (REPO / 'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest()
    if source['runtime_manifest_sha256'] != current:
        raise ValueError('Refreshed short draft does not bind the active runtime')
    namespace = runpy.run_path(str(BASE), run_name='c150142_refresh_driver')
    variables = namespace['run'].__globals__
    variables.update(SOURCE=SOURCE, SCRATCH=SCRATCH,
                     PORTABLE=PORTABLE, INDEX=INDEX)
    result = namespace['run'](limit)
    index = json.loads(INDEX.read_text())
    for row in index['rows']:
        receipt = json.loads((WORK / row['receipt']).read_text())
        if receipt['runtime_manifest_sha256'] != current:
            raise ValueError('Refreshed proof binds another runtime: ' + row['case_id'])
    result['runtime_manifest_sha256'] = current
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    print(json.dumps(run(args.limit), sort_keys=True))
