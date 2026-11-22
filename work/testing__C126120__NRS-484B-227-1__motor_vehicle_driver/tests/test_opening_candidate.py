"""Exercise both concrete engineering scenes and exact source rejection."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from runner import main
from uturn_control import validate_scene


class OpeningCandidateTests(unittest.TestCase):
    def check(self, path):
        with patch.object(sys, "argv", ["runner.py", "--scene", str(path), "--check"]):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                main()
        return json.loads(out.getvalue())

    def test_exact_single_and_multiple_constructions(self):
        root = ET.parse(HERE / "candidate-median-opening.xodr").getroot()
        self.assertEqual([road.attrib["id"] for road in root.findall("road")], ["10", "20"])
        self.assertEqual([road.find("./lanes/laneSection/right/lane").attrib["type"]
                          for road in root.findall("road")], ["driving", "driving"])
        paths = [HERE / "scene.json", HERE / "cases/opening_multiple/scene.json"]
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(self.check(path)["static_construction_valid"])
        single, multiple = [json.loads(path.read_text()) for path in paths]
        self.assertEqual(single["context"], multiple["context"])
        self.assertEqual(validate_scene(single)["reverse_segments"], [])
        self.assertEqual(validate_scene(multiple)["reverse_segments"], [4])

    def test_changed_map_bytes_rejected(self):
        scene = json.loads((HERE / "scene.json").read_text())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scene["reviewed_context_source"] = str(HERE / "candidate-reviewed-median.json")
            scene["authority_review_source"] = str(HERE / "candidate-authority-review.json")
            scene["map_source"] = str(root / "candidate-median-opening.xodr")
            (root / "candidate-median-opening.xodr").write_bytes(
                (HERE / "candidate-median-opening.xodr").read_bytes() + b" ")
            (root / "scene.json").write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, "OpenDRIVE source hash"):
                self.check(root / "scene.json")


if __name__ == "__main__":
    unittest.main()
