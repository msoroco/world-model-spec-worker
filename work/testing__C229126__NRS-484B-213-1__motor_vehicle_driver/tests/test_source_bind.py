import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "source_bind.py"
spec = importlib.util.spec_from_file_location("source_bind", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SourceBindTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.packet = {"case_id": "assignment__occluded_left",
                       "actors": {"ego": {}, "overtaken": {}, "oncoming": {}},
                       "road": {}, "sources": []}
        roles = module.REQUIRED | {"oncoming_vehicle", "opaque_blocker"}
        for role in sorted(roles):
            body = b"<OpenDRIVE/>" if role == "map" else role.encode()
            path = self.root / (role + ".txt")
            path.write_bytes(body)
            digest = hashlib.sha256(body).hexdigest()
            self.packet["sources"].append({"role": role, "path": path.name, "sha256": digest})
            if role == "map": self.packet["map_opendrive_sha256"] = digest
            if role == "centerline": self.packet["road"]["centerline_source_sha256"] = digest

    def test_all_original_bytes_bound(self):
        result = module.bind(self.packet, self.root)
        self.assertEqual(set(result), module.REQUIRED | {"oncoming_vehicle", "opaque_blocker"})

    def test_changed_source_rejected(self):
        (self.root / "centerline.txt").write_text("changed")
        with self.assertRaisesRegex(ValueError, "source bytes changed"):
            module.bind(self.packet, self.root)

    def test_missing_occluder_source_rejected(self):
        self.packet["sources"] = [r for r in self.packet["sources"] if r["role"] != "opaque_blocker"]
        with self.assertRaisesRegex(ValueError, "opaque blocker original source"):
            module.bind(self.packet, self.root)


if __name__ == "__main__": unittest.main()
