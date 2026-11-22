from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from map_inventory import inventory


class MapInventoryTests(unittest.TestCase):
    def test_records_junction_road_and_signal_without_scope_inference(self):
        source = '<OpenDRIVE><road id="1" name="A" length="10" junction="-1">' \
                 '<planView><geometry s="0" x="2" y="3" hdg="0" length="10"><line/></geometry></planView>' \
                 '<lanes><laneSection s="0"><right><lane id="-1" type="driving"/></right></laneSection></lanes>' \
                 '<signals><signal id="7" type="206" name="candidate" s="5" t="1"/></signals>' \
                 '</road><junction id="4"><connection id="0" incomingRoad="1" connectingRoad="2"/></junction></OpenDRIVE>'
        with TemporaryDirectory() as directory:
            path = Path(directory) / "map.xodr"
            path.write_text(source)
            result = inventory(path)
            self.assertEqual(result["roads"][0]["signals"][0]["id"], "7")
            self.assertEqual(result["roads"][0]["lanes"][0]["type"], "driving")
            self.assertEqual(result["junctions"][0]["connections"][0]["incomingRoad"], "1")
            self.assertTrue(any("does not prove" in item for item in result["limitations"]))

    def test_duplicate_road_id_rejected(self):
        source = '<OpenDRIVE>' + 2*('<road id="1"><planView><geometry s="0" x="0" y="0" hdg="0" length="1"><line/></geometry></planView></road>') + '</OpenDRIVE>'
        with TemporaryDirectory() as directory:
            path = Path(directory) / "map.xodr"
            path.write_text(source)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                inventory(path)


if __name__ == "__main__": unittest.main()
