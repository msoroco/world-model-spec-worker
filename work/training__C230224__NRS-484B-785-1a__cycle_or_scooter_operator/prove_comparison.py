"""Exercise controlled comparison and rejection paths with temporary sources."""
import json
import os
from pathlib import Path
import tempfile

from audit_comparison import audit
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
        fixture(root/'high', 17*.44704, 'controlled_2')
        low, high = measure(root/'low'), measure(root/'high')
        accepted = audit(low, high, original_only=False)
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
        try:
            audit(low, high)
        except ValueError as exc:
            assert 'Original Native measurements required' in str(exc)
        else:
            raise AssertionError('Synthetic fixtures accepted as original Native evidence')
        print(json.dumps({'comparison': accepted, 'negative_checks': 5}, sort_keys=True))


if __name__ == '__main__':
    main()
