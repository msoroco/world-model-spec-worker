"""Conditional semantic activation is tied to the reviewed source preflight."""
import json
import hashlib
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from activate_reviewed_semantic import activate
from reviewed_delivery_author import author
from test_reviewed_delivery_author import fixture


class ActivateReviewedSemanticTest(unittest.TestCase):
    def test_source_bound_positive_and_changed_receipt_negative(self):
        assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
        with TemporaryDirectory(dir=REPO / ".runtime-work") as source, \
             TemporaryDirectory(dir=REPO / ".runtime-work") as candidate, \
             TemporaryDirectory(dir=REPO / ".runtime-work") as preflight:
            fixture(source)
            output = Path(candidate) / "candidate"
            receipts = Path(preflight) / "preflight"
            author(source, ROOT / "candidate-map.xodr", output, receipts, scratch_output=True)
            result = activate(output, assignment)
            self.assertEqual(result["selected_cases"], 7)
            self.assertEqual(result["stage_count"], 7)
            index = json.loads((output / "proposals/semantic-index.json").read_text())
            self.assertEqual(index["assignment_id"], ROOT.name)
            receipt = receipts / "precedence/preflight.json"
            content = json.loads(receipt.read_text())
            content["map_sha256"] = "0" * 64
            receipt.write_text(json.dumps(content))
            with self.assertRaisesRegex(ValueError, "does not bind original packet and map"):
                activate(output, assignment)

    def test_rejects_forged_route_binding(self):
        assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
        with TemporaryDirectory(dir=REPO / ".runtime-work") as source, \
             TemporaryDirectory(dir=REPO / ".runtime-work") as candidate, \
             TemporaryDirectory(dir=REPO / ".runtime-work") as preflight:
            fixture(source)
            output = Path(candidate) / "candidate"
            receipts = Path(preflight) / "preflight"
            author(source, ROOT / "candidate-map.xodr", output, receipts, scratch_output=True)
            receipt = receipts / "precedence/preflight.json"
            content = json.loads(receipt.read_text())
            content["route_binding"]["ego"]["road_sequence"] = ["31", "31", "31"]
            receipt.write_text(json.dumps(content))
            with self.assertRaisesRegex(ValueError, "lacks exact route binding"):
                activate(output, assignment)

    def test_rejects_changed_inline_review_source(self):
        assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
        with TemporaryDirectory(dir=REPO / ".runtime-work") as source, \
             TemporaryDirectory(dir=REPO / ".runtime-work") as candidate, \
             TemporaryDirectory(dir=REPO / ".runtime-work") as preflight:
            fixture(source)
            output = Path(candidate) / "candidate"
            author(source, ROOT / "candidate-map.xodr", output,
                   Path(preflight) / "preflight", scratch_output=True)
            construction = output / "precedence/construction.json"
            document = json.loads(construction.read_text())
            scene = json.loads(next(item["content"] for item in document["files"]
                                    if item["path"] == "scene.json"))
            packet = json.loads(next(item["content"] for item in document["files"]
                                     if item["path"] == scene["reviewed_context_source"]))
            source_name = packet["law_context"]["public_access_source"]["source_path"]
            next(item for item in document["files"]
                 if item["path"] == source_name)["content"] = "changed reviewed bytes\n"
            construction.write_text(json.dumps(document, sort_keys=True) + "\n")
            index_path = output / "candidate-index.json"
            index = json.loads(index_path.read_text())
            next(item for item in index["cases"] if item["case_id"].endswith("__precedence"))[
                "construction_sha256"] = hashlib.sha256(construction.read_bytes()).hexdigest()
            index_path.write_text(json.dumps(index, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "inline reviewed source differs from preflight"):
                activate(output, assignment)

    def test_rejects_stale_runtime_and_nonpreflight_receipt(self):
        assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
        with TemporaryDirectory(dir=REPO / ".runtime-work") as source, \
             TemporaryDirectory(dir=REPO / ".runtime-work") as candidate, \
             TemporaryDirectory(dir=REPO / ".runtime-work") as preflight:
            fixture(source)
            output = Path(candidate) / "candidate"
            receipts = Path(preflight) / "preflight"
            author(source, ROOT / "candidate-map.xodr", output, receipts, scratch_output=True)
            index_path = output / "candidate-index.json"
            index = json.loads(index_path.read_text())
            index["runtime_manifest_sha256"] = "0" * 64
            index_path.write_text(json.dumps(index, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "runtime binding changed"):
                activate(output, assignment)
            index["runtime_manifest_sha256"] = hashlib.sha256(
                (REPO / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest()
            index_path.write_text(json.dumps(index, sort_keys=True) + "\n")
            receipt = receipts / "precedence/preflight.json"
            content = json.loads(receipt.read_text())
            content["native_started"] = True
            receipt.write_text(json.dumps(content, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "does not bind original packet and map"):
                activate(output, assignment)


if __name__ == "__main__":
    unittest.main()
