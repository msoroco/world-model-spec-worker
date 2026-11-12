"""Run pinned candidate invariants for nine unselected speed alternatives."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.candidate_constructions import validate


def main():
    manifest = json.loads((ROOT / 'through-speed-compatibility-manifest.json').read_text())
    receipts = []
    for entry in manifest['cases']:
        result = validate(ROOT, entry, 'NRS-484B-257-1', 'C158190',
                          required=False, candidate_count=4)
        assert result['fallbacks'] == ['fallback1', 'fallback2', 'fallback3']
        speed_probe = next(item for item in entry['candidates'] if item['id'] == 'fallback3')
        assert speed_probe['trigger']['source'] == 'interaction_history.jsonl'
        assert 'through' in speed_probe['trigger']['metric']
        receipts.append(result)
    report = {'format': 'c158190-through-speed-fallback-structure-proof',
              'cases': receipts, 'pinned_invariants_passed': True,
              'exact_offline_compatibility_saved_proofs_in_separate_receipts': True,
              'native_feasibility_proven': False}
    (ROOT / 'through-speed-fallback-structure-proof.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': len(receipts), 'fallbacks': 9}))


if __name__ == '__main__':
    main()
