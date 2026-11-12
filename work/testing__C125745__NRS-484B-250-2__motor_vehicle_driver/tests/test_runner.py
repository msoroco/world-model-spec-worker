import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runner import ASSIGNMENT,load_config,_context
from capture_sources import CAMERAS
from test_median_route_control import scene


class RunnerTests(unittest.TestCase):
    def packet(self,root):
        site=scene()
        site['native_map_name']='TownReviewed'
        site['intersection_id']=44
        site['camera_poses']={name:[0,0,8,0,-25,0] for name in CAMERAS}
        site['source_refs']={name:'review/'+name for name in (
            'crossing_geometry_source','all_entrances_source',
            'sign_governance_source','sign_face_video_source',
            'median_spacing_source')}
        for role,road in (('ego',1),('other',2)):
            site['approaches'][role]['road_id']=road
            site['approaches'][role]['spawn_pose']=[0,0,0,0]
        packet=root/'site.json';packet.write_text(json.dumps(site))
        cfg={'assignment_id':ASSIGNMENT,'law_id':'NRS-484B-250-2',
             'cell_id':'C125745','actor':'motor_vehicle_driver',
             'selected_case_id':ASSIGNMENT+'__stop_ego_left_near_time',
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
            self.assertEqual(context['native_stop_sign_id'],17)
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

if __name__=='__main__':unittest.main()
