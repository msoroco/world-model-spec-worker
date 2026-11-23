import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from reviewed_context import REQUIRED
from taxi_runner import check_attempt, check_materialized_bundle, check_static


class NativeEntrypointPreflightTest(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="c150530-preflight-", dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        sources = self.output / "reviewed_sources"
        sources.mkdir()
        refs = {}
        for key in REQUIRED:
            source = sources / (key + ".txt")
            quote = "synthetic fixture " + key
            source.write_text(quote + "\n")
            refs[key] = {"path": "reviewed_sources/" + source.name,
                         "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                         "record_id": "fixture-" + key,
                         "review_note": "synthetic CPU fixture only", "quote": quote}
        map_path = ROOT / "candidates/near_stand.xodr"
        layout = json.loads((ROOT / "candidates/near_stand.json").read_text())
        self.packet = self.output / "reviewed-context.json"
        self.data = {"format": "c150530-reviewed-context-v1",
                     "assignment_id": "testing__C150530__LVMC-11-60-090__taxi_driver",
                     "case_id": "testing__C150530__LVMC-11-60-090__taxi_driver__near_stand",
                     "law_id": "LVMC-11-60-090", "actor": "taxi_driver",
                     "map_sha256": hashlib.sha256(map_path.read_bytes()).hexdigest(),
                     "stand_center_m": layout["stand"]["center"],
                     "notice_point_m": layout["posted_notice"]["point"],
                     "notice_meaning": "right turn at first street intersection",
                     "sources": refs}
        self.packet.write_text(json.dumps(self.data))

    def test_exact_candidate_and_retained_context_are_accepted(self):
        output, packet, map_path, layout_path = check_attempt(self.output, self.packet,
                                                               "near_stand")
        self.assertEqual(output, self.output.resolve())
        self.assertEqual(packet, self.packet.resolve())
        self.assertEqual(map_path.name, "near_stand.xodr")
        self.assertEqual(layout_path.name, "near_stand.json")

    def test_missing_original_context_is_rejected(self):
        self.packet.unlink()
        with self.assertRaisesRegex(ValueError, "retained in attempt"):
            check_attempt(self.output, self.packet, "near_stand")

    def test_reused_native_attempt_is_rejected(self):
        (self.output / "overview.mkv").write_text("prior acquisition")
        with self.assertRaisesRegex(ValueError, "already used"):
            check_attempt(self.output, self.packet, "near_stand")

    def test_cross_case_packet_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "identity differs"):
            check_attempt(self.output, self.packet, "far_stand")

    def test_check_cli_is_cpu_only(self):
        result = subprocess.run([sys.executable, str(ROOT / "taxi_runner.py"),
                                 "--check", "--case", "near_stand"],
                                capture_output=True, text=True,
                                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["native_started"])
        self.assertTrue(check_static("near_stand")["static_construction_valid"])

    def test_materialized_bundle_inventory_rejects_stale_runner(self):
        files = {}
        for name in ("candidates/near_stand.xodr", "candidates/near_stand.json"):
            source = ROOT / name
            target = self.output / name
            target.parent.mkdir(exist_ok=True)
            target.write_text(source.read_text())
            files[name] = target.read_text()
        files["config.json"] = json.dumps({
            "selected_case_id": "testing__C150530__LVMC-11-60-090__taxi_driver__near_stand"})
        files["runner.py"] = (ROOT / "taxi_runner.py").read_text()
        for name in ("config.json", "runner.py"):
            (self.output / name).write_text(files[name])
        (self.output / "construction.json").write_text(json.dumps({
            "case_id": "testing__C150530__LVMC-11-60-090__taxi_driver__near_stand",
            "files": [{"path": name, "content": content}
                      for name, content in files.items()]}))
        check_materialized_bundle(self.output, "near_stand")
        (self.output / "runner.py").write_text("changed runner\n")
        with self.assertRaisesRegex(ValueError, "bundle source missing or changed: runner.py"):
            check_materialized_bundle(self.output, "near_stand")


if __name__ == "__main__":
    unittest.main()
