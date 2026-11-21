import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_semantic_cases as semantic


class SemanticCellGuardTest(unittest.TestCase):
    def test_missing_other_vehicle_rejects_law_case_build(self):
        source = semantic.load_rows

        def without_follower(*args):
            rows = source(*args)
            changed = [dict(row) for row in rows]
            first = dict(changed[0]['scene_actor_inventory'])
            first['actors'] = [actor for actor in first['actors']
                               if actor.get('type_id') != 'vehicle.synthetic_follower']
            changed[0]['scene_actor_inventory'] = first
            return changed

        with patch.object(semantic, 'load_rows', side_effect=without_follower):
            with self.assertRaisesRegex(ValueError, 'focal actor'):
                semantic.build()


if __name__ == '__main__':
    unittest.main()
