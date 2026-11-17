import json,hashlib,tempfile,unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from traffic_spec_adapter.environment_measurements import load
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class RelocationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve()
  (self.root/'road.xodr').write_text('road');(self.root/'asset').write_bytes(b'original material')
  self.surface={'schema':'authored-native-road-surface-v1','ice_or_snow':False,'map_sha256':sha(self.root/'road.xodr'),'authorship':'synthetic','source_assets':[{'path':'/unavailable/source.asset','sha256':sha(self.root/'asset')}]}
  self.write('surface_provenance.json',self.surface)
  self.write('environment_calibration.json',{'schema':'rendered-target-contrast-range-v1','passed':True,'distance_kind':'sampled_lower_bound','visibility_m':10,'samples':[]})
  self.relocations={'surface_provenance_sha256':sha(self.root/'surface_provenance.json'),'paths':{'/unavailable/source.asset':'asset'}};self.write('asset_relocations.json',self.relocations)
 def write(self,name,data):(self.root/name).write_text(json.dumps(data))
 def test_source_receipt_preserved(self):self.assertEqual(load(self.root)['surface_sha256'],sha(self.root/'surface_provenance.json'))
 def test_changed_snapshot_rejected(self):
  (self.root/'asset').write_text('changed')
  with self.assertRaisesRegex(ValueError,'asset changed'):load(self.root)
 def test_wrong_source_receipt_rejected(self):
  self.relocations['surface_provenance_sha256']='0'*64;self.write('asset_relocations.json',self.relocations)
  with self.assertRaisesRegex(ValueError,'another source receipt'):load(self.root)
 def test_escaped_asset_rejected(self):
  self.relocations['paths']['/unavailable/source.asset']='../asset';self.write('asset_relocations.json',self.relocations)
  with self.assertRaisesRegex(ValueError,'escapes capture'):load(self.root)
