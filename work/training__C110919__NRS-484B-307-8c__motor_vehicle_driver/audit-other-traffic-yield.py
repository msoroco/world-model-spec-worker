"""Independent replay and mutation audit for retained other-traffic histories."""
import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
import other_traffic_yield


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cases = {}
    for case in ('probe_a', 'probe_b'):
        ego = HERE / 'native/fixtures' / (case + '-480.json')
        traffic = HERE / 'native/fixtures' / (case + '-other-traffic-480.json')
        ego_data = json.loads(ego.read_text())
        data = json.loads(traffic.read_text())
        assert data['case'] == case and len(data['frames']) == len(ego_data['frames']) == 480
        assert [r['frame'] for r in data['frames']] == list(range(480))
        assert [r['conflict_occupied'] for r in data['frames']] == [135 <= i <= 155 for i in range(480)]
        entry = next(i for i, row in enumerate(ego_data['frames']) if row['ego_turn_entered'])
        assert entry == 181
        result = other_traffic_yield.inspect(ego, sha(ego), traffic, sha(traffic))
        assert result['turn_entry_frame'] == entry
        assert result['last_other_traffic_conflict_frame'] == 155
        assert result['other_traffic_clearance_s'] == 1.3
        assert result['legal_verdict'] is None and not result['original_native_observed']
        rejected = []
        for label in ('late_conflict', 'wrong_actor', 'unknown_lawful_status', 'broken_frame_join'):
            altered = copy.deepcopy(data)
            if label == 'late_conflict':
                altered['frames'][entry]['conflict_occupied'] = True
            elif label == 'wrong_actor':
                altered['frames'][entry]['actor_id'] = 205
            elif label == 'unknown_lawful_status':
                altered['frames'][entry]['lawful_intersection_user'] = None
            else:
                altered['frames'][entry]['native_frame'] += 1
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'other-traffic.json'
                path.write_text(json.dumps(altered, separators=(',', ':')) + '\n')
                try:
                    other_traffic_yield.inspect(ego, sha(ego), path, sha(path))
                except ValueError:
                    rejected.append(label)
                else:
                    raise AssertionError('Altered other-traffic source accepted: ' + label)
        assert len(rejected) == 4
        cases[case] = {'ego_sha256': sha(ego), 'other_traffic_sha256': sha(traffic),
                       'turn_entry_frame': entry, 'last_conflict_frame': 155,
                       'clearance_s': 1.3, 'mutation_rejections': rejected}
    runner = (HERE / 'native/runner.py').read_text()
    finalizer = (HERE / 'native/finalize.py').read_text()
    assert 'other_traffic_history.jsonl' in runner and 'other_traffic_history.jsonl' in finalizer
    assert 'measure_other_traffic_yield' in finalizer
    saved = json.loads((HERE / 'native/saved-fixture-proof.log').read_text())
    assert {r['case'] for r in saved['results']} == {'probe_a', 'probe_b'}
    assert all(r['positive_exit_code'] == 0 and r['negative_exit_code'] != 0 and
               r['traffic_mutation_exit_code'] != 0 and r['other_traffic_history_joined']
               for r in saved['results'])
    receipt = {'format': 'c110919-other-traffic-yield-cpu-proof-v1', 'passed': True,
               'cases': cases, 'source_kind': 'synthetic_cpu',
               'authored_in_native_runner_and_finalizer': True,
               'synthetic_saved_finalization_verified': True,
               'original_native_or_legal_acceptance': False}
    (HERE / 'other-traffic-yield-audit.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
