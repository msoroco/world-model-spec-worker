"""Source-bound positive and altered-condition comparison probes."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREFIX='testing__C10808__LVMC-11-40-080__cycle_or_scooter_operator__'
import sys
sys.path.insert(0,str(ROOT))
from test_delivery_audit import DeliveryAuditTests, write
import delivery_audit
import comparison_audit


class SealedComparisonTests(unittest.TestCase):
    def pair(self,base):
        left=DeliveryAuditTests().fixture(base/'left',PREFIX+'dismount_before_uturn')
        right=DeliveryAuditTests().fixture(base/'right',PREFIX+'mounted_uturn')
        return left,right

    def run_pair(self,left,right):
        return comparison_audit.audit_sealed_pair(
            left[0],left[1],left[2],right[0],right[1],right[2],
            media_verify=lambda *args,**kwargs:True)

    def test_positive_sealed_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);(base/'left').mkdir();(base/'right').mkdir()
            left,right=self.pair(base)
            self.assertTrue(self.run_pair(left,right)['passed'])

    def test_changed_scene_rejected_after_reseal(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);(base/'left').mkdir();(base/'right').mkdir()
            left,right=self.pair(base)
            sign=delivery_audit.read(right[0]/'sign-inventory.json')
            sign['fixed_scene_sha256']='different-scene';write(right[0]/'sign-inventory.json',sign)
            acquisition=delivery_audit.read(right[0]/'acquisition.json')
            acquisition['sign-inventory.json']['sha256']=delivery_audit.sha(right[0]/'sign-inventory.json')
            write(right[0]/'acquisition.json',acquisition)
            seal=delivery_audit.read(right[0]/'capture-seal.json')
            seal['sources']['sign-inventory.json']=delivery_audit.sha(right[0]/'sign-inventory.json')
            write(right[0]/'capture-seal.json',seal)
            write(right[0]/'native-exit.json',{'event':'native_exit',
                'capture_seal_sha256':delivery_audit.sha(right[0]/'capture-seal.json')})
            write(right[0]/'owner-release.json',{'event':'owner_released',
                'operator_attested':True,
                'native_exit_sha256':delivery_audit.sha(right[0]/'native-exit.json')})
            with self.assertRaisesRegex(ValueError,'fixed condition.*fixed_scene'):
                self.run_pair(left,right)

    def test_missing_dismount_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);(base/'left').mkdir();(base/'right').mkdir()
            left,right=self.pair(base)
            events=delivery_audit.rows(left[0]/'phase-events.jsonl')
            events[1]['phase']='mounted_reversal'
            (left[0]/'phase-events.jsonl').write_text(''.join(
                __import__('json').dumps(row)+'\n' for row in events))
            with self.assertRaisesRegex(ValueError,'sealed original missing or changed'):
                self.run_pair(left,right)


if __name__=='__main__':unittest.main()
