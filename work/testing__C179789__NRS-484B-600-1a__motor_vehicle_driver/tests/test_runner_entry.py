import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('runner',ROOT/'runner.py')
RUNNER=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(RUNNER)


class RunnerEntryTests(unittest.TestCase):
    def test_selected_surface_seed_copied_and_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'surface-seed.txt').write_text('reviewed source fixture\n')
            source = RUNNER.prepare_surface_source(root)
            self.assertEqual(source.read_text(), 'reviewed source fixture\n')
            self.assertEqual(RUNNER.prepare_surface_source(root), source)
            source.write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'differs from selected construction'):
                RUNNER.prepare_surface_source(root)

    def config(self):
        return {'law_id':'NRS-484B-600-1a','cell_id':'C179789',
                'actor':'motor_vehicle_driver','selected_case_id':RUNNER.CASES[0],
                'supported_case_ids':list(RUNNER.CASES), 'rate_hz':20,'duration_s':45,
                'site_packet':'road_packet.json','required_atoms':[],
                'condition_target':{'surface':'dry','lane_width_m':[3,4],
                    'longitudinal_body_gap_m':[10,35],
                    'sight_distance_m':[10,120],'precipitation_percent':[0,5]},
                'cameras':[{'name':name,'width':size[0],'height':size[1],
                            'fov_deg':90} for name,size in RUNNER.PROFILE.items()]}

    def test_exact_inventory_and_camera_profile(self):
        self.assertEqual(RUNNER.validate_config(self.config())['duration_s'],45)
        bad=self.config();bad['cameras']=bad['cameras'][:3]
        with self.assertRaisesRegex(ValueError,'Four ordered'):
            RUNNER.validate_config(bad)
        bad=self.config();bad['selected_case_id']='wrong'
        with self.assertRaisesRegex(ValueError,'Eight exact'):
            RUNNER.validate_config(bad)

    def test_case_condition_targets_reject_wrong_physical_observation(self):
        target=self.config()['condition_target']
        row={'surface':'dry','lane_width_m':3.3,'sight_distance_m':80,
             'precipitation_percent':0,
             'surrounding_traffic':[{'longitudinal_body_gap_m':20}]}
        self.assertTrue(RUNNER.verify_observed_target(row,target))
        row['sight_distance_m']=25
        self.assertTrue(RUNNER.verify_observed_target(row,target))
        row['sight_distance_m']=5
        with self.assertRaisesRegex(ValueError,'sight_distance_m'):
            RUNNER.verify_observed_target(row,target)
        row['sight_distance_m']=80
        row['lane_width_m']=2.6
        with self.assertRaisesRegex(ValueError,'lane_width_m'):
            RUNNER.verify_observed_target(row,target)
        row['lane_width_m']=3.3
        row['surface']='ice_or_snow'
        with self.assertRaisesRegex(ValueError,'surface differs'):
            RUNNER.verify_observed_target(row,target)
        row['surface']='dry'
        fog_target=dict(target,fog_density_percent=[70,90],fog_distance_m=[10,30])
        row.update(fog_density_percent=80,fog_distance_m=20)
        self.assertTrue(RUNNER.verify_observed_target(row,fog_target))
        row['fog_density_percent']=0
        with self.assertRaisesRegex(ValueError,'fog_density_percent'):
            RUNNER.verify_observed_target(row,fog_target)

    def test_site_source_hashes_required(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            surface='Original pavement observation fixture\n'
            profile=dict(zip(('cloudiness','precipitation','wetness',
                'fog_density','fog_distance','sun_altitude_angle'),(0,0,0,0,100,30)))
            weather=json.dumps({'native_map_id':'FixtureMap','weather_profile':profile})+'\n'
            (root/'surface.txt').write_text(surface)
            (root/'weather.txt').write_text(weather)
            (root/'surface_packet.json').write_text(json.dumps({
                'review_status':'reviewed_native_surface','native_map_id':'FixtureMap','road_id':7,'surface':'dry',
                'reviewer':'fixture reviewer','review_basis':'fixture declaration',
                'source':{'path':'surface.txt','sha256':hashlib.sha256(surface.encode()).hexdigest()}}))
            packet={'review_status':'reviewed_native_road_site',
                    'reviewer':'fixture reviewer','road_review_basis':'fixture declaration',
                    'traffic_review_basis':'fixture declaration','camera_review_basis':'fixture declaration',
                    'native_map_id':'FixtureMap','vehicle_blueprint_id':'vehicle.fixture',
                    'lead_blueprint_id':'vehicle.fixture','case_id':RUNNER.CASES[0],
                    'road_id':7,'lane_id':-1,'surface_packet':'surface_packet.json',
                    'weather_profile_source':{'path':'weather.txt','sha256':hashlib.sha256(weather.encode()).hexdigest()},
                    'weather_profile':profile,
                    'ego_spawn':{'x':0,'y':0,'z':.3,'yaw_deg':0},
                    'lead_spawn':{'x':20,'y':0,'z':.3,'yaw_deg':0},
                    'ego_target_speed_mps':8,'lead_target_speed_mps':7}
            surface_review,weather_ref=RUNNER.require_site_packet(packet,root,RUNNER.CASES[0])
            self.assertEqual(surface_review['surface'],'dry')
            self.assertEqual(weather_ref['path'],'weather.txt')
            changed_surface=json.loads((root/'surface_packet.json').read_text())
            changed_surface['road_id']=8
            (root/'surface_packet.json').write_text(json.dumps(changed_surface))
            with self.assertRaisesRegex(ValueError,'map/road identity differs'):
                RUNNER.require_site_packet(packet,root,RUNNER.CASES[0])
            changed_surface['road_id']=7
            (root/'surface_packet.json').write_text(json.dumps(changed_surface))
            (root/'weather.txt').write_text('changed\n')
            with self.assertRaisesRegex(ValueError,'hash changed'):
                RUNNER.require_site_packet(packet,root,RUNNER.CASES[0])

    def test_diagnostic_packet_refused_before_carla_import(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)
            (output/'construction.json').write_text('{}\n')
            (output/'surface-seed.txt').write_text('Synthetic diagnostic surface\n')
            (output/'road_packet.json').write_text(json.dumps({
                'review_status':'synthetic diagnostic','case_id':RUNNER.CASES[0]})+'\n')
            with self.assertRaisesRegex(ValueError,'before capture'):
                RUNNER.capture(NS(output_dir=str(output)),self.config())


if __name__=='__main__':unittest.main()
