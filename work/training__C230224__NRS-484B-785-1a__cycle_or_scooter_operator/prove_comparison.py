"""Exercise controlled comparison and rejection paths with temporary sources."""
import json
import os
from pathlib import Path
import tempfile

from audit_comparison import audit, audit_boundary, audit_selected_pair, AID
from measure_scooter import measure
from prove_scooter import fixture


def rejected(low, high, fragment):
    try:
        audit(low, high, original_only=False)
    except ValueError as exc:
        assert fragment in str(exc), (fragment, str(exc))
        return
    raise AssertionError('Defective comparison accepted: ' + fragment)


def main():
    with tempfile.TemporaryDirectory(prefix='scooter-comparison-', dir=os.environ['TMPDIR']) as tmp:
        root = Path(tmp)
        fixture(root/'low', 12*.44704, 'controlled_1')
        fixture(root/'at', 15*.44704, 'controlled_at_cap')
        fixture(root/'high', 17*.44704, 'controlled_2')
        low, high = measure(root/'low'), measure(root/'high')
        at_cap = measure(root/'at')
        accepted = audit(low, high, original_only=False)
        boundary = audit_boundary(low, at_cap, high, original_only=False)
        assert boundary['at_cap_above_15_mph_frames'] == 0
        pair_results = [audit_selected_pair(a, b, AID + '__' + name, original_only=False)
                        for a, b, name in ((low, high, 'comparison'),
                                           (low, at_cap, 'below_vs_requested_at_cap'),
                                           (at_cap, high, 'requested_at_cap_vs_above'))]
        assert all(row['fixed_context_checked'] and row['legal_result'] is None
                   for row in pair_results)
        changed = json.loads(json.dumps(high))
        changed['fixed_context']['ordinance_review_source'] = 'different ordinance'
        rejected(low, changed, 'fixed path, device or ordinance')
        changed = json.loads(json.dumps(high))
        changed['above_15_mph_frames'] = 599
        rejected(low, changed, 'does not stay above')
        changed = json.loads(json.dumps(low))
        changed['path_center_frames'] = 599
        rejected(changed, high, 'path occupancy incomplete')
        changed = json.loads(json.dumps(high))
        del changed['source_sha256']['native_rider_trace.jsonl']
        rejected(low, changed, 'source hashes missing')
        changed = json.loads(json.dumps(at_cap))
        changed['requested_speed_mps'] = 17*.44704
        try:
            audit_boundary(low, changed, high, original_only=False)
        except ValueError as exc:
            assert 'exact 15 mph request' in str(exc)
        else:
            raise AssertionError('Wrong at-cap request accepted')
        try:
            audit(low, high)
        except ValueError as exc:
            assert 'Original Native measurements required' in str(exc)
        else:
            raise AssertionError('Synthetic fixtures accepted as original Native evidence')
        print(json.dumps({'comparison': accepted, 'boundary': boundary,
                          'selected_pairs': pair_results,
                          'negative_checks': 6}, sort_keys=True))


if __name__ == '__main__':
    main()
