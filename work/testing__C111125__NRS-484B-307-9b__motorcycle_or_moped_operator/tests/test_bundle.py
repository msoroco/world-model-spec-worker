import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case_binding(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_unsourced_capture_rejected(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Reviewed original C111125"):
                runner.main()

    def test_pinned_capture_dispatch_to_operator_session(self):
        case_id = runner.check()
        session = types.SimpleNamespace(restoration_verified=True)
        context = MagicMock()
        context.__enter__.return_value = session
        adapter = types.SimpleNamespace(open_session=MagicMock(return_value=context))
        exchange = types.ModuleType("worker_exchange")
        output = types.ModuleType("worker_exchange.native_output")
        output.seal_capture = MagicMock()
        env = {"SCENARIO_SITE_PACKET": "/reviewed/site.json", "SCENARIO_NATIVE_ADAPTER": "test_native_adapter"}
        args = ["runner.py", "--output-dir", "/materialized/attempt",
                "--host", "localhost", "--port", "2000"]
        with patch.dict("os.environ", env), patch.dict(sys.modules, {"test_native_adapter": adapter,
                "worker_exchange": exchange, "worker_exchange.native_output": output}), \
                patch("native_session.capture_events") as capture, patch("sys.argv", args):
            runner.main()
        adapter.open_session.assert_called_once_with(case_id, "/reviewed/site.json", "localhost", 2000)
        capture.assert_called_once_with(session, "/reviewed/site.json", case_id, "/materialized/attempt")
        output.seal_capture.assert_called_once()


if __name__ == "__main__":
    unittest.main()
