import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from traffic_spec_adapter.native_control_observations import read_observations,project
from traffic_spec_adapter.atom_contract import required_coverage


class NativeControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.xml='<OpenDRIVE><road id="1"><lanes><laneSection/></lanes></road><road id="2"><lanes><laneSection/></lanes></road><junction id="10"><connection incomingRoad="1" connectingRoad="2"><laneLink from="-1" to="-1"/></connection></junction></OpenDRIVE>'
        self.code='original executed inventory producer\n';self.code_hash=hashlib.sha256(self.code.encode()).hexdigest();self.map_hash=hashlib.sha256(self.xml.encode()).hexdigest()
        self.write('road.xodr',self.xml,raw=True);self.write('runner.py',self.code,raw=True)
        self.write('construction.json',{'files':[{'path':'runner.py','content':self.code}]})
        self.write('result.json',{'completion':{'binding':{'source':'original'}}})
        self.write('native_incoming_lane_topology.json',{'schema':'native-incoming-lane-topology-v1','map_sha256':self.map_hash,'instrumentation_sha256':self.code_hash,'connections':[{'incoming_road':1,'incoming_lane':-1,'connecting_road':2,'incoming_observed':True,'connected_junction_observed':True}]})
        self.row={'schema':'native-control-inventory-v1','frame':7,'time_s':.05,'map_sha256':self.map_hash,'instrumentation_sha256':self.code_hash,'scope':'entire_recorded_world','map_name':'Carla/Maps/OpenDriveMap','api_queries':['World.get_actors','World.get_environment_objects:TrafficLight','World.get_environment_objects:TrafficSigns'],'traffic_actor_inventory':[],'environment_light_inventory':[],'environment_sign_inventory':[],'unclassified_actor_types':[]}
        self.save_row();self.telemetry=[{'frame':7,'time_s':.05}];self.regions=[{'id':1,'kind':'lane','lane':{'enters_intersection':23}},{'id':2,'kind':'lane','lane':{}}];self.scene={'devices':[],'structures':self.regions,'users':[]}
        self.verify=patch('batch_pipeline.completion.verify');self.verify.start();self.addCleanup(self.verify.stop)
    def write(self,name,value,raw=False):
        (self.root/name).write_text(value if raw else json.dumps(value))
    def save_row(self):self.write('native_control_inventory.jsonl',json.dumps(self.row)+'\n',raw=True)
    def read(self):return read_observations(self.root,self.telemetry,{(1,0,-1):1},self.regions,{'dev.traffic_signal','st.lane_enters'})
    def test_closed_full_scope_receipts_cover_absence_and_all_incoming_links(self):
        obs=self.read();project(self.scene,'st.lane_enters',obs['st.lane_enters'][0])
        result=required_coverage(set(obs),{'atoms':{k:'exact' for k in obs}},[self.scene],obs)
        self.assertTrue(result['passed'])
        self.assertFalse(required_coverage(set(obs),{'atoms':{k:'exact' for k in obs}},[self.scene])['passed'])
    def test_missing_original_packet_never_gains_retrospective_absence(self):
        (self.root/'native_control_inventory.jsonl').unlink();self.assertEqual(self.read(),{})
    def test_bad_frame_or_unknown_entities_block(self):
        for key,value in [('frame',8),('scope','local_crop'),('unclassified_actor_types',['static.unknown']),('environment_light_inventory',[{'id':1}])]:
            old=self.row[key];self.row[key]=value;self.save_row()
            with self.assertRaises(ValueError):self.read()
            self.row[key]=old
    def test_missing_or_wrong_incoming_core_reference_blocks(self):
        obs=self.read();self.scene['structures'][0]['lane'].pop('enters_intersection')
        with self.assertRaises(ValueError):project(self.scene,'st.lane_enters',obs['st.lane_enters'][0])
    def test_contradicting_signal_cannot_be_hidden_by_absence_receipt(self):
        obs=self.read();self.scene['devices']=[{'kind':'traffic_signal'}]
        with self.assertRaises(ValueError):project(self.scene,'dev.traffic_signal',obs['dev.traffic_signal'][0])
