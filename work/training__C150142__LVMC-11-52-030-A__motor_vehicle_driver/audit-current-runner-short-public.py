"""Run pinned receipt and candidate validators on the 14 fresh short cases."""

import json
from pathlib import Path
import sys


WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.candidate_constructions import validate as validate_candidates
from worker_exchange.package_compatibility import check_receipts


def run():
    manifest = json.loads((WORK / 'current-runtime-runner-short-bound-manifest.json').read_text())
    index = json.loads((WORK / 'current-runtime-runner-short-public-index.json').read_text())
    suffixes = {'reference'} | {row['case_id'].removeprefix(WORK.name + '__')
                                for row in index['rows']}
    entries = [entry for entry in manifest['cases']
               if entry['case_id'].removeprefix(WORK.name + '__') in suffixes]
    if len(entries) != 14 or len(suffixes) != 14:
        raise ValueError('Expected exact 14 short cases')
    subset = dict(manifest, cases=entries)
    check_receipts(REPO, WORK, subset)
    for entry in entries:
        construction = json.loads((WORK / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        validate_candidates(WORK, entry, config['law_id'], config['cell_id'],
                            required=True, require_alternate=True,
                            candidate_count=4)
    return {'format': 'c150142-current-runner-short-public-audit-v1',
            'passed': True, 'case_count': len(entries),
            'candidate_count': len(entries) * 4,
            'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
