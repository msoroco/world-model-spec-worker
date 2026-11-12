"""Selected queue identity and safety checks; no dispatch is attempted."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("queue_intent", HERE / "audit-queue-intent.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class QueueIntentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queue = json.loads(module.QUEUE.read_text())
        cls.manifest = json.loads((HERE / "execution-manifest.json").read_text())
        cls.plan = json.loads((HERE / "case-plan.json").read_text())

    def test_current_selected_rows_and_legacy_format(self):
        report = module.audit(self.queue, self.manifest, self.plan)
        self.assertEqual(len(report["cases"]), 2)
        self.assertFalse(report["dispatchable"])
        self.assertFalse(report["canonical_format_ready"])

    def test_wrong_case_and_early_release_rejected(self):
        for edit in (lambda row: row.update(dispatchable=True),
                     lambda row: row.update(capture_command="python3.11 runtime.py capture --case other")):
            queue = copy.deepcopy(self.queue)
            row = next(item for item in queue["cases"] if item["assignment_id"] == HERE.name)
            edit(row)
            with self.assertRaises(ValueError):
                module.audit(queue, self.manifest, self.plan)


if __name__ == "__main__":
    unittest.main()
