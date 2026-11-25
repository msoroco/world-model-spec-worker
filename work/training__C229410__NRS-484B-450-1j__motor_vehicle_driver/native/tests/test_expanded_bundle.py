import json
from pathlib import Path
import unittest

import runner
from branch_variants import BRANCHES
from expanded_layout import check as layout_check


class ExpandedBundleTests(unittest.TestCase):
    def test_exact_branch_and_two_sided_geometry(self):
        config = json.loads(Path("config.json").read_text())
        branch = BRANCHES[config["case_suffix"]]
        self.assertEqual(config["initial_activity"], branch.activity)
        self.assertEqual(config["exception_context"], branch.exception)
        self.assertEqual(config["selected_case_id"], config["case_id"])
        self.assertTrue(layout_check()["two_opposing_lanes"])
        self.assertFalse(runner.check()["physical_acceptance_claimed"])
