"""Check the exact external-packet Native bundle without fixture source bytes."""
import json
from pathlib import Path
import unittest

from parking_runner import check_materialized_package
from source_review import validate


class ExternalPacketBundle(unittest.TestCase):
    def test_materialized_identity_and_external_source_boundary(self):
        scene = json.loads(Path("scene.json").read_text())
        check_materialized_package(Path.cwd(), scene)
        self.assertFalse(Path("reviewed-context.json").exists())
        with self.assertRaises(FileNotFoundError):
            validate("reviewed-context.json", source_root=Path.cwd())
        changed = dict(scene, case_id=scene["case_id"] + "_changed")
        with self.assertRaisesRegex(ValueError, "source-bound scene differs"):
            check_materialized_package(Path.cwd(), changed)


if __name__ == "__main__":
    unittest.main()
