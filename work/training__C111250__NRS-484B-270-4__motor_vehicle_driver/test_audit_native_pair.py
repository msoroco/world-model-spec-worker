import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
spec = importlib.util.spec_from_file_location("audit_native_pair", HERE / "audit-native-pair.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PairAuditTest(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work"; scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="c111250-pair-negative-", dir=scratch)
        self.root = Path(self.temp.name)
        self.p = self.root / "p"; self.c = self.root / "c"
        for suffix, target in (("controlled_1", self.p), ("controlled_2", self.c)):
            target.mkdir()
            source = HERE / ("native-diagnostic-" + suffix + "-sources")
            for name in ("facility-context.json", "subsection3-context.json",
                         "road.xodr", "video_frames.jsonl", "body-history.jsonl"):
                shutil.copy2(source / name, target / name)

    def tearDown(self):
        self.temp.cleanup()

    def test_positive_and_changed_context(self):
        self.assertTrue(module.audit_sources(self.p, self.c)["passed"])
        path = self.c / "subsection3-context.json"
        value = json.loads(path.read_text()); value["exception_legally_resolved"] = True
        path.write_text(json.dumps(value) + "\n")
        with self.assertRaisesRegex(ValueError, "fixed source differs"):
            module.audit_sources(self.p, self.c)

    def test_missing_crossing_rejected(self):
        path = self.p / "body-history.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            for point in row["body_xy_m"]:
                point[0] = 1.75
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        with self.assertRaisesRegex(ValueError, "not measured"):
            module.audit_sources(self.p, self.c)


if __name__ == "__main__":
    unittest.main()
