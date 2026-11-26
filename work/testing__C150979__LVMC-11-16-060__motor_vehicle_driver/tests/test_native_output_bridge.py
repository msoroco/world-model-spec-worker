import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import native_output_bridge as bridge


class NativeBridgeTest(unittest.TestCase):
    def test_restoration_and_source_inventory_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "restoration"):
                bridge.publish(root, map_bytes=b"map", restored=False)
            (root / "inventory.json").write_text(json.dumps({"frame_count": 900,
                "sources": {}}) + "\n")
            with self.assertRaisesRegex(ValueError, "source inventory"):
                bridge.publish(root, map_bytes=b"map", restored=True)
