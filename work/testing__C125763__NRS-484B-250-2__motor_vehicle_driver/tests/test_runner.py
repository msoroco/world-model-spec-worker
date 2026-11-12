import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runner import ASSIGNMENT,load_config,_context,_native_approaches
from capture_sources import CAMERAS
from test_median_yield_route import scene
from site_packet import SOURCE_CLAIMS


class RunnerTests(unittest.TestCase):
    def packet(self,root):
        site=scene()
        site['format']='worker-yield-median-site-review'
        site['review_status']='reviewed_candidate'
        site['native_map_name']='TownReviewed'
        site['intersection_id']=44
        site['all_entrance_road_lanes']=[[1,1],[2,1]]
        site['camera_poses']={name:[0,0,8,0,-25,0] for name in CAMERAS}
        for role,road in (('ego',1),('other',2)):
            site['approaches'][role]['road_id']=road
            site['approaches'][role]['spawn_pose']=[0,0,0,0]
        (root/'review').mkdir(exist_ok=True)
        site['source_refs']={}
        site['source_documents']={}
        for role,keys in SOURCE_CLAIMS.items():
            relative='review/'+role+'.json'
            document={'format':'worker-yield-median-site-source',
                      'source_role':role,'review_basis':'synthetic CPU fixture',
                      'reviewed_site_fields':{key:site[key] for key in keys}}
            source_path=root/relative
            source_path.write_text(json.dumps(document))
            site['source_refs'][role]=relative
            site['source_documents'][role]={'path':relative,
                'sha256':hashlib.sha256(source_path.read_bytes()).hexdigest()}
        packet=root/'site.json';packet.write_text(json.dumps(site))
        cfg={'assignment_id':ASSIGNMENT,'law_id':'NRS-484B-250-2',
             'cell_id':'C125763','actor':'motor_vehicle_driver',
             'selected_case_id':ASSIGNMENT+'__yield_ego_left_near_time',
             'rate_hz':20,'frames':900,'duration_s':45,'other_release_frame':40,
             'required_atoms':[],'recording_description':{},'site_packet':{'path':'site.json',
                'sha256':hashlib.sha256(packet.read_bytes()).hexdigest()}}
        config=root/'config.json';config.write_text(json.dumps(cfg))
        return config,packet,cfg,site

    def test_cpu_checked_packet_and_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            config,_,_,_=self.packet(Path(tmp))
            cfg,site=load_config(config)
            context=_context(site)
            self.assertEqual(context['native_yield_sign_id'],17)
            self.assertEqual(context['ego_highway_id'],'EW')
            self.assertEqual(cfg['frames'],900)
            self.assertFalse(context['physical_acceptance_claimed'])

    def test_cli_check_does_not_start_carla(self):
        with tempfile.TemporaryDirectory() as tmp:
            config,_,_,_=self.packet(Path(tmp))
            completed=subprocess.run([sys.executable,str(ROOT/'runner.py'),
                                      '--config',str(config),'--check'],
                                     text=True,capture_output=True,check=True)
            report=json.loads(completed.stdout)
            self.assertEqual(report['planned_frames'],900)
            self.assertEqual(len(report['named_source_cameras']),4)
            self.assertFalse(report['carla_started'])

    def test_materialized_offline_check_reads_local_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.packet(root)
            completed=subprocess.run([sys.executable,str(ROOT/'runner.py'),'--check'],
                                     cwd=root,text=True,capture_output=True,check=True)
            self.assertTrue(json.loads(completed.stdout)['cpu_check_passed'])

    def test_stale_packet_and_wrong_case_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config,packet,cfg,_=self.packet(root)
            packet.write_text(packet.read_text()+'\n')
            with self.assertRaisesRegex(ValueError,'SHA mismatch'):
                load_config(config)
            config,_,cfg,_=self.packet(root)
            cfg['selected_case_id']=ASSIGNMENT+'__invented_case'
            config.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError,'assignment identity'):
                load_config(config)

    def test_missing_camera_pose_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config,packet,cfg,site=self.packet(root)
            del site['camera_poses']['approach']
            packet.write_text(json.dumps(site))
            cfg['site_packet']['sha256']=hashlib.sha256(packet.read_bytes()).hexdigest()
            config.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError,'Four named camera poses'):
                load_config(config)

    def test_changed_or_unreviewed_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config,packet,cfg,site=self.packet(root)
            source=root/site['source_refs']['sign_governance_source']
            source.write_text(source.read_text()+'\n')
            with self.assertRaisesRegex(ValueError,'SHA mismatch'):
                load_config(config)
            config,packet,cfg,site=self.packet(root)
            site['yield_sign']['native_id']=999
            packet.write_text(json.dumps(site))
            cfg['site_packet']['sha256']=hashlib.sha256(packet.read_bytes()).hexdigest()
            config.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError,'differs from reviewed source'):
                load_config(config)

    def test_unstructured_packet_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config,packet,cfg,site=self.packet(root)
            site['review_status']='draft'
            packet.write_text(json.dumps(site))
            cfg['site_packet']['sha256']=hashlib.sha256(packet.read_bytes()).hexdigest()
            config.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError,'Structured reviewed'):
                load_config(config)

    def test_both_native_lanes_and_yield_entrance_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            config,_,_,site=self.packet(Path(tmp))
            poses={role:NS(location=NS(x=x,y=y,z=0)) for role,(x,y) in
                   {'ego':(0,0),'other':(15,-15)}.items()}
            lanes={(0,0):(1,1),(15,-15):(2,1),(8,0):(1,1)}
            def waypoint(location,project_to_road=False):
                road,lane=lanes[(location.x,location.y)]
                return NS(road_id=road,lane_id=lane,transform=NS(location=location))
            world_map=NS(get_waypoint=waypoint)
            carla=NS(Location=lambda **kwargs:NS(**kwargs))
            _,entrance=_native_approaches(world_map,poses,site,carla)
            self.assertEqual(entrance.transform.location.x,8)
            lanes[(15,-15)]=(3,1)
            with self.assertRaisesRegex(ValueError,'other Native spawn road/lane'):
                _native_approaches(world_map,poses,site,carla)
            lanes[(15,-15)]=(2,1)
            lanes[(8,0)]=(1,2)
            with self.assertRaisesRegex(ValueError,'Native yield entrance road/lane'):
                _native_approaches(world_map,poses,site,carla)

if __name__=='__main__':unittest.main()
