import importlib.util
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest
from test_outside_lane import m as crossing, rows as source_rows

folder=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('saved_audit_c3997',folder/'saved_audit.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)

class Tests(unittest.TestCase):
 def test_sealed_original_history_and_missing_source(self):
  case=crossing.CASES[0]
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'original.jsonl'
   rows=source_rows(case,900)
   for row in rows:row['capture_packet_sha256']='packet'
   def write():
    path.write_text(''.join(json.dumps(x)+'\n' for x in rows))
    return sha256(path.read_bytes()).hexdigest()
   digest=write()
   self.assertEqual(m.audit_history(path,digest,case.name,'map-source')['frame_count'],900)
   with self.assertRaisesRegex(ValueError,'hash mismatch'):
    m.audit_history(path,'0'*64,case.name,'map-source')
   rows[499]['capture_packet_sha256']=''
   digest=write()
   with self.assertRaisesRegex(ValueError,'capture packet source missing'):
    m.audit_history(path,digest,case.name,'map-source')
   rows[499]['capture_packet_sha256']='packet';rows[499]['original_frame']=999
   digest=write()
   with self.assertRaisesRegex(ValueError,'original-frame join mismatch'):
    m.audit_history(path,digest,case.name,'map-source')

if __name__=='__main__':unittest.main()
