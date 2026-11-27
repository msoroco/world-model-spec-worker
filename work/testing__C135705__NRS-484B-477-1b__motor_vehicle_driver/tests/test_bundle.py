"""Materialized source-gated Native bundle identity checks."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import runner


class BundleTests(unittest.TestCase):
    def test_exact_selected_case(self):
        case_id,config=runner.check(Path(__file__).resolve().parents[1])
        self.assertEqual(case_id,config['selected_case_id'])

    def test_reviewed_source_required_before_carla(self):
        with patch('sys.argv',['runner.py','--host','localhost','--port','2000',
                               '--output-dir','.']):
            with patch.dict('os.environ',{},clear=True):
                with self.assertRaisesRegex(ValueError,'source-hashed alley site'):
                    runner.main()


if __name__=='__main__':unittest.main()
