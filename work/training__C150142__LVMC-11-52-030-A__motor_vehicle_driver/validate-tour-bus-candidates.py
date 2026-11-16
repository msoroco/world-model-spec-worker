"""Check the exact four candidate identities and durable offline receipts."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.candidate_constructions import validate
from worker_exchange.common import sha


def main():
    manifest = json.loads((ROOT / 'execution-manifest-diagnostic-tour_bus_below-draft.json').read_text())
    entry = manifest['cases'][0]
    for candidate in [entry, *entry['candidates']]:
        proof = candidate['offline']
        if proof['exit_code'] != 0 or proof['construction_sha256'] != candidate['construction_sha256']:
            raise ValueError('Offline proof is not bound to candidate')
        if sha(ROOT / proof['log']) != proof['log_sha256'] or \
           sha(ROOT / proof['wrapper_log']) != proof['wrapper_log_sha256']:
            raise ValueError('Offline proof logs changed')
    result = validate(ROOT, entry, 'LVMC-11-52-030-A', 'C150142',
                      required=False, require_alternate=True, candidate_count=4)
    print(json.dumps({'candidate_validation': result,
                      'offline_proof_logs_source_bound': True}, sort_keys=True))


if __name__ == '__main__':
    main()
