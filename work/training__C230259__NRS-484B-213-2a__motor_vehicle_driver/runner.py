"""Root index for six exact selected Native constructions.

Use runtime.py capture with the execution manifest and one exact --case for
acquisition. This index never treats its multi-case config as an acquisition.
"""
import argparse
import json
from pathlib import Path


def check(bundle):
    bundle = Path(bundle)
    config = json.loads((bundle / 'config.json').read_text())
    manifest = json.loads((bundle / 'execution-manifest.json').read_text())
    cases = [entry['case_id'] for entry in manifest['cases']]
    if config.get('supported_case_ids') != cases or len(cases) != 6:
        raise ValueError('Root index differs from exact selected cases')
    if config.get('original_native_observed') is not False:
        raise ValueError('Root index cannot claim Native observation')
    return {'case_ids': cases, 'frames_per_case': 600,
            'native_executed': False, 'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--bundle', type=Path, default=Path.cwd())
    args = parser.parse_args()
    if not args.check:
        parser.error('Use runtime.py capture --manifest execution-manifest.json --case EXACT_ID')
    print(json.dumps(check(args.bundle)))
