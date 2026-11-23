import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import crosswalk as c

P = [[0,0],[4,0],[4,4],[0,4]]

def ref(root, name, value):
    raw = json.dumps(value).encode()
    (root/name).write_bytes(raw)
    return {'path':name, 'sha256':hashlib.sha256(raw).hexdigest()}

class Fake:
    def __init__(self): self.calls=[]
    def verify_crosswalk(self, x): self.calls.append('verify'); return {'map_name':x['map_name'],'crosswalk_polygon':x['crosswalk_polygon']}
    def spawn_vehicle(self, x, p): self.calls.append('spawn'); return {'actor_id':'ego','blueprint':x['blueprint']}
    def configure_route(self, *a): self.calls.append('route')
    def configure_exception(self, *a): self.calls.append('exception')

class TestCrosswalk(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.site={'cell_id':'C214977','layout':'residence_district','map_name':'Town','highway_source':'native_map',
                   'frontage_source':'survey','crosswalk_source':'native_map','marking_status_source':'native_map',
                   'signal_governance_source':'native_device','crosswalk_polygon':P,'parking_route':[[-5,2],[2,2]]}
        self.vehicle={'blueprint':'vehicle.sedan','driver_source':'assigned actor'}
        self.case={'case_id':'on_park','action':'park','exception':'none','destination':[2,2]}
    def tearDown(self): self.tmp.cleanup()
    def test_construction(self):
        adapter=Fake(); out=c.construct(adapter,ref(self.root,'site.json',self.site),ref(self.root,'vehicle.json',self.vehicle),self.case,self.root)
        self.assertEqual(out['subject_id'],'ego'); self.assertEqual(adapter.calls,['verify','spawn','route','exception'])
    def test_missing_site_source(self):
        x=dict(self.site); x['frontage_source']=''
        with self.assertRaisesRegex(c.SourceError,'residence source'): c.construct(Fake(),ref(self.root,'site.json',x),ref(self.root,'vehicle.json',self.vehicle),self.case,self.root)
    def test_hash_rejection(self):
        r=ref(self.root,'site.json',self.site); (self.root/'site.json').write_text('{}')
        with self.assertRaisesRegex(c.SourceError,'hash'): c.sealed_json(r,self.root)
    def test_crosswalk_geometry(self):
        self.assertTrue(c.footprint_relation([[1,1],[3,1],[3,3],[1,3]],P)['contained'])
        self.assertTrue(c.footprint_relation([[-1,1],[1,1],[1,2],[-1,2]],P)['overlap'])
        self.assertFalse(c.footprint_relation([[5,5],[6,5],[6,6],[5,6]],P)['overlap'])
    def row(self,i):
        return {'frame':100+i,'time_s':i*.05,'case_id':'on_park','subject_id':'ego','speed_mps':0.0,
                'halt_activity':'park','body_corners_xy':[[1,1],[3,1],[3,3],[1,3]],'crosswalk_id':'cw',
                'marking_status':'marked','traffic_conflict':False,'law_direction':False,
                'police_direction':False,'device_direction':False}
    def expected(self,n): return {'frame_count':n,'first_frame':100,'case_id':'on_park','subject_id':'ego','crosswalk_id':'cw','marking_status':'marked','crosswalk_polygon':P,'action':'park'}
    def test_measure(self):
        rows=[self.row(i) for i in range(3)]
        m=c.measure(rows,self.expected(3)); self.assertEqual(m['halt_contained_crosswalk_frames'],3); self.assertIsNone(m['legal_judgment'])
    def test_measure_exception(self):
        rows=[self.row(i) for i in range(3)]; rows[1]['traffic_conflict']=True
        self.assertEqual(c.measure(rows,self.expected(3))['halt_with_exception_source_frames'],1)
    def test_measure_rejects_gap(self):
        rows=[self.row(i) for i in range(3)]; rows[1]['time_s']=0.2
        with self.assertRaisesRegex(c.SourceError,'20 Hz'): c.measure(rows,self.expected(3))
    def test_measure_rejects_unknown_exception(self):
        rows=[self.row(i) for i in range(3)]; del rows[1]['law_direction']
        with self.assertRaises(KeyError): c.measure(rows,self.expected(3))
    def test_saved_source(self):
        rows=[self.row(i) for i in range(900)]
        mapping=[{'frame':r['frame'],'time_s':r['time_s']} for r in rows]
        rr=ref(self.root,'rows.json',rows); mr=ref(self.root,'map.json',mapping)
        cams={name:{**ref(self.root,name+'.json',{'frame_count':900}),'frame_count':900,'fps':20} for name in ('front','rear','left','right')}
        attempt={'source_format':'native_original','fps':20,'frame_count':900,'actor_rows':rr,'frame_map':mr,'cameras':cams,'expected':self.expected(900)}
        self.assertEqual(c.audit_saved(attempt,self.root)['measurement']['halt_frames'],900)
        attempt['cameras'].pop('rear')
        with self.assertRaisesRegex(c.SourceError,'four-camera'): c.audit_saved(attempt,self.root)
    def test_comparison(self):
        a={'case_id':'a','map':'Town','destination':'on'}; b={'case_id':'b','map':'Town','destination':'off'}
        self.assertEqual(c.audit_comparison(a,b,['map'],['destination'])['differences_checked'],['destination'])
        b['map']='Other'
        with self.assertRaisesRegex(c.SourceError,'fixed condition'): c.audit_comparison(a,b,['map'],['destination'])

if __name__=='__main__': unittest.main()
