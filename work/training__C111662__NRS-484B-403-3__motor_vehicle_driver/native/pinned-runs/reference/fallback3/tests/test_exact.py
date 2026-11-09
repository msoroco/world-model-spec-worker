import json
import sys
import tempfile
import unittest
from pathlib import Path

root=Path.cwd()
native=root/'work'/'training__C111662__NRS-484B-403-3__motor_vehicle_driver'/'native'
sys.path.insert(0,str(native))
from check import check
from saved import make_raw,process
from capture import control

class ExactTurn(unittest.TestCase):
    def setUp(self):
        self.bundle=native/'drafts'/'reference'/'fallback3'

    def test_source_bound_request(self):
        result=check(self.bundle)
        self.assertEqual(result['frames'],800)
        self.assertFalse(result['delivery_ready'])

    def test_synthetic_saved_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'raw.json'
            path.write_text(json.dumps(make_raw(self.bundle)))
            result=process(self.bundle,path)
            self.assertEqual(result['frames_joined'],800)
            self.assertFalse(result['district_designation_verified'])

    def test_rehashed_road_mutation_rejected(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)
            for item in self.bundle.iterdir():
                (target/item.name).write_bytes(item.read_bytes())
            road=target/'district-crossroads.xodr'
            road.write_text(road.read_text().replace('x="-100"','x="-99"',1))
            cfg=json.loads((target/'config.json').read_text())
            cfg['road_sha256']=hashlib.sha256(road.read_bytes()).hexdigest()
            (target/'config.json').write_text(json.dumps(cfg))
            with self.assertRaises(ValueError):check(target)
