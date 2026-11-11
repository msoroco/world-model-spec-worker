import copy
import importlib.util
from pathlib import Path
import sys
import unittest

NATIVE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NATIVE))
from frontage import authored_plan
from audit_frontage_original import inspect


def readback(width=5):
    plan = authored_plan()
    intervals = [[x-width/2, x+width/2] for x in plan['station_x_m']]
    return {'format':'c111662-native-frontage-readback-v1',
            'source_kind':'original_native_geometry',
            'blueprint_id':'static.prop.shop_frontage',
            'actor_ids':list(range(100,120)),
            'native_actor_intervals_x_m':intervals,
            'native_frontage_m':100 if width==5 else width*20,
            'district_designation_verified':False,
            'building_use_legally_verified':False,'legal_verdict':None}


class FrontageAuditTests(unittest.TestCase):
    def test_sufficient_readback_shape(self):
        result=inspect(authored_plan(),readback())
        self.assertEqual(result['actor_count'],20)
        self.assertEqual(result['native_frontage_m'],100)
        self.assertFalse(result['district_designation_verified'])

    def test_short_or_duplicate_readback_rejected(self):
        with self.assertRaisesRegex(ValueError,'below 300 feet'):
            inspect(authored_plan(),readback(3))
        bad=readback();bad['actor_ids'][1]=bad['actor_ids'][0]
        with self.assertRaisesRegex(ValueError,'inventory incomplete'):
            inspect(authored_plan(),bad)

    def test_stale_station_and_legal_claim_rejected(self):
        bad=readback();bad['native_actor_intervals_x_m'][0]=[-100,-99]
        with self.assertRaisesRegex(ValueError,'misses station'):
            inspect(authored_plan(),bad)
        bad=readback();bad['district_designation_verified']=True
        with self.assertRaisesRegex(ValueError,'unsupported legal claim'):
            inspect(authored_plan(),bad)


if __name__=='__main__':unittest.main()
