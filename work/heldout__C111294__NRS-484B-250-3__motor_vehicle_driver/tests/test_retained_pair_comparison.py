import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controlled_pair_binding import bind_pair
from highway_continuity_comparison_audit import require_retained_pair_bindings
from test_controlled_pair_binding import pair


class RetainedPairComparisonTests(unittest.TestCase):
    def test_matching_original_bindings_and_rejections(self):
        binding = bind_pair(pair())
        self.assertEqual(require_retained_pair_bindings(binding, copy.deepcopy(binding)),
                         binding['route_pair_sha256'])
        changed = copy.deepcopy(binding)
        changed['routes']['other'][1]['lane_id'] = -2
        with self.assertRaisesRegex(ValueError, 'Stale'):
            require_retained_pair_bindings(binding, changed)
        changed = bind_pair(pair())
        changed['map_name'] = 'DifferentMap'
        import hashlib, json
        payload = {key: value for key, value in changed.items()
                   if key != 'route_pair_sha256'}
        changed['route_pair_sha256'] = hashlib.sha256(json.dumps(
            payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'Changed'):
            require_retained_pair_bindings(binding, changed)
        with self.assertRaisesRegex(ValueError, 'Missing'):
            require_retained_pair_bindings(binding, {})


if __name__ == '__main__':
    unittest.main()
