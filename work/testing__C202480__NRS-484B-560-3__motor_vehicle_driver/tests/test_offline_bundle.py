"""Check that the selected exact Native bundle stays tied to its case plan."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from runner import check_construction


HERE = Path(__file__).resolve().parents[1]


class OfflineBundleTests(unittest.TestCase):
    def test_selected_case_and_camera_contract(self):
        result = check_construction(HERE / "config.json", HERE / "case-plan.json")
        self.assertTrue(result["construction_checked"])
        self.assertFalse(result["reviewed_site_checked"])
        self.assertFalse(result["physical_acceptance_claimed"])

    def test_rejects_changed_case_and_camera(self):
        config = json.loads((HERE / "config.json").read_text())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            for changed, message in (({"case": {}}, "selected case"),
                                     ({"cameras": []}, "camera")):
                altered = copy.deepcopy(config)
                altered.update(changed)
                path.write_text(json.dumps(altered), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    check_construction(path, HERE / "case-plan.json")

    def test_supplied_site_runs_production_gate(self):
        packet = Path("reviewed-site-packet.json")
        with patch("runner.verify_site") as gate:
            result = check_construction(HERE / "config.json", HERE / "case-plan.json", packet)
        gate.assert_called_once_with(packet, HERE / "case-plan.json", result["case_id"])


if __name__ == "__main__":
    unittest.main()
