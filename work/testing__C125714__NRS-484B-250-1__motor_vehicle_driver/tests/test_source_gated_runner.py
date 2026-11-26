"""A selected scene can be checked, but synthetic packets cannot launch Native."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from source_gated_runner import check_scene, reviewed_source


class SourceGatedRunnerTest(unittest.TestCase):
    def test_selected_scene_and_reviewed_source_gate(self):
        scene = json.loads((ROOT / "scene.json").read_text())
        scene["diagnostic_only"] = False
        scene.pop("reviewed_context_source", None)
        scene.pop("reviewed_context_sha256", None)
        self.assertEqual(check_scene(scene)["case_id"], scene["case_id"])
        with self.assertRaisesRegex(ValueError, "source-hashed"):
            reviewed_source(scene, None, None)
        with TemporaryDirectory() as directory:
            source = Path(directory) / "packet.json"
            packet = json.loads((ROOT / "diagnostic-context.json").read_text())
            packet["diagnostic_only"] = True
            source.write_text(json.dumps(packet) + "\n")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "synthetic diagnostic packet"):
                reviewed_source(scene, str(source), digest)
            packet["diagnostic_only"] = False
            packet["case_id"] = scene["case_id"]
            source.write_text(json.dumps(packet) + "\n")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(reviewed_source(scene, str(source), digest)[1], digest)
            with self.assertRaisesRegex(ValueError, "hash differs"):
                reviewed_source(scene, str(source), "0" * 64)
            packet["case_id"] = "another-case"
            source.write_text(json.dumps(packet) + "\n")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "case differs"):
                reviewed_source(scene, str(source), digest)


if __name__ == "__main__":
    unittest.main()
