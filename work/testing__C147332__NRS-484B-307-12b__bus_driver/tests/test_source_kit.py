import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source-kit"))
from acquire_source_packet import stage
from probe_native_asset import probe
from bind_asset_probe import bind


KIT = Path(__file__).resolve().parents[1] / "source-kit"


class SourceKitTest(unittest.TestCase):
    def test_asset_probe_binding_preserves_pending_review_and_source_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = {"route": "fixture route", "travel_direction": "northbound",
                    "milepost_or_cross_streets": "fixture marker",
                    "gantry_or_device_id": "fixture gantry",
                    "bus_approach": "fixture bus approach", "governed_lane": "red_lane"}
            for name in ("highway", "official_device"):
                (root / (name + ".source")).write_text(name + " fixture bytes")
            from hashlib import sha256
            draft = {"format": "worker-red-x-source-draft-v1",
                     "review_status": "pending_independent_review", "site": site}
            for name in ("highway", "official_device"):
                source = root / (name + ".source")
                draft[name] = {"source_path": source.name,
                               "source_sha256": sha256(source.read_bytes()).hexdigest(),
                               "reviewer": None}
            draft_path, probe_path, output = (root / "draft-context.json",
                                               root / "probe.json", root / "binding.json")
            draft_path.write_text(json.dumps(draft))
            receipt = {"blueprint_id": "static.fixture_red_x", "attribute": "display_state",
                       "red_x_value": "red_x", "blueprint_readback": True,
                       "rendered_pixels_reviewed": False,
                       "official_device_design_reviewed": False}
            probe_path.write_text(json.dumps(receipt))
            binding = bind(draft_path, probe_path, output)
            self.assertEqual(binding["review_status"], "pending_independent_review")
            self.assertEqual(binding["native_asset_blueprint_id"], receipt["blueprint_id"])
            self.assertIn("rendered_red_x_pixels", binding["review_required"])
            with self.assertRaisesRegex(ValueError, "already exists"):
                bind(draft_path, probe_path, output)
            receipt["rendered_pixels_reviewed"] = True
            probe_path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "unreviewed red-X blueprint"):
                bind(draft_path, probe_path, root / "changed.json")
            receipt["rendered_pixels_reviewed"] = False
            probe_path.write_text(json.dumps(receipt))
            (root / "official_device.source").write_text("changed source")
            with self.assertRaisesRegex(ValueError, "missing or changed"):
                bind(draft_path, probe_path, root / "changed.json")

    def test_imported_blueprint_probe_checks_mutable_red_x_state(self):
        class Attribute:
            is_modifiable = True
            recommended_values = ["off", "red_x"]
            def __init__(self, value): self.value = value
            def __str__(self): return self.value
        class Blueprint:
            def __init__(self): self.attribute = Attribute("off")
            def has_attribute(self, name): return name == "display_state"
            def get_attribute(self, name): return self.attribute
            def set_attribute(self, name, value): self.attribute.value = value
        class Library:
            def __init__(self): self.blueprint = Blueprint()
            def find(self, name):
                if name != "static.fixture_red_x": raise KeyError(name)
                return self.blueprint
        library = Library()
        receipt = probe(library, "static.fixture_red_x")
        self.assertTrue(receipt["blueprint_readback"])
        self.assertFalse(receipt["rendered_pixels_reviewed"])
        with self.assertRaisesRegex(ValueError, "unavailable"):
            probe(library, "static.missing")
        with self.assertRaisesRegex(ValueError, "exact imported static"):
            probe(library, "fixture.red_x_asset")
        library.blueprint.attribute.is_modifiable = False
        with self.assertRaisesRegex(ValueError, "not modifiable"):
            probe(library, "static.fixture_red_x")
        library.blueprint.attribute.is_modifiable = True
        library.blueprint.attribute.recommended_values = ["off"]
        with self.assertRaisesRegex(ValueError, "allowed display state"):
            probe(library, "static.fixture_red_x")

    def test_red_x_art_is_explicit_unimported_source(self):
        spec = json.loads((KIT / "native-red-x-display.json").read_text())
        self.assertEqual(spec["status"], "source_art_only_unimported")
        self.assertTrue(spec["physical_import_required"])
        self.assertTrue(spec["official_device_design_match_review_required"])
        svg = ET.parse(KIT / spec["face_source"]).getroot()
        self.assertEqual(svg.attrib["viewBox"], "0 0 1024 1024")
        paths = svg.findall("{http://www.w3.org/2000/svg}path")
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].attrib["stroke"], "#ff0000")
        self.assertEqual(paths[0].attrib["d"].count("M "), 2)

    def test_draft_requires_exact_site_and_cannot_claim_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "highway.txt").write_text("fixture highway bytes")
            (root / "device.txt").write_text("fixture device bytes")
            site = {"route": "fixture route", "travel_direction": "northbound",
                    "milepost_or_cross_streets": "fixture marker", "gantry_or_device_id": "fixture gantry",
                    "bus_approach": "fixture bus approach", "governed_lane": "red_lane"}
            docs = {key: {"local_path": str(root / filename), "citation": "fixture only",
                          "acquired_from": "fixture only"}
                    for key, filename in (("highway", "highway.txt"),
                                          ("official_device", "device.txt"))}
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"site": site, "documents": docs}))
            packet = stage(manifest, root / "retained")
            self.assertEqual(packet["review_status"], "pending_independent_review")
            self.assertIsNone(packet["official_device"]["reviewer"])
            self.assertEqual((root / "retained" / "highway.source").read_text(),
                             "fixture highway bytes")
            with self.assertRaisesRegex(ValueError, "empty"):
                stage(manifest, root / "retained")
            site.pop("gantry_or_device_id")
            manifest.write_text(json.dumps({"site": site, "documents": docs}))
            with self.assertRaisesRegex(ValueError, "exact highway site"):
                stage(manifest, root / "new")
            site["gantry_or_device_id"] = "fixture gantry"
            linked = root / "linked-device.txt"
            linked.symlink_to(root / "device.txt")
            docs["official_device"]["local_path"] = str(linked)
            manifest.write_text(json.dumps({"site": site, "documents": docs}))
            with self.assertRaisesRegex(ValueError, "symlinked"):
                stage(manifest, root / "new")


if __name__ == "__main__":
    unittest.main()
