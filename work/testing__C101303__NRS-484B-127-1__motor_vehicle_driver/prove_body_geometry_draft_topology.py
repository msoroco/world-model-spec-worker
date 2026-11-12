"""Check the eight draft primary/fallback case topologies."""
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / 'runtime'))
from scenario_pipeline.worker_exchange.candidate_constructions import validate


def main():
    manifest = json.loads((ROOT / 'body-geometry-all-draft-manifest.json').read_text())
    if len(manifest['cases']) != 8:
        raise ValueError('Expected eight exact selected cases')
    for case in manifest['cases']:
        validate(ROOT, case, 'NRS-484B-127-1', 'C101303', required=False,
                 require_alternate=True, candidate_count=4)
        print(case['case_id'], 'topology_passed')


if __name__ == '__main__':
    main()
