import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from source_binding import verify_site_sources


class SourceBindingTests(unittest.TestCase):
    def test_positive_and_missing_tampered_collapsed_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = root / "site.json"
            route = root / "route.json"
            aisle = root / "aisle.json"
            route.write_text("review candidate route\n", encoding="utf-8")
            aisle.write_text("review candidate aisle\n", encoding="utf-8")
            ref = lambda path: {"path": path.name,
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            source = {"route_source_ref": ref(route),
                      "access_aisle_source_ref": ref(aisle)}
            self.assertEqual(set(verify_site_sources(source, packet)), set(source))
            route.write_text("changed route\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 differs"):
                verify_site_sources(source, packet)
            route.unlink()
            with self.assertRaisesRegex(ValueError, "source file missing"):
                verify_site_sources(source, packet)
            source["route_source_ref"] = source["access_aisle_source_ref"]
            with self.assertRaisesRegex(ValueError, "must be distinct"):
                verify_site_sources(source, packet)

    def test_opaque_reference_is_not_source_binding(self):
        with self.assertRaisesRegex(ValueError, "path and SHA-256"):
            verify_site_sources({"route_source_ref": "reviewed route"},
                                Path("site.json"))


if __name__ == "__main__":
    unittest.main()
