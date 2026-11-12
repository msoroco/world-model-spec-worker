import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from native_station_survey import verify, load_and_verify

def ref(road,lane,s): return {'road_id':road,'lane_id':lane,'s':s}
SURVEY={'public_before':ref(7,1,0),'public_at':ref(7,1,8),
        'public_after':ref(7,1,16),'driveway_at':ref(8,2,6)}

class NativeStationSurveyTest(unittest.TestCase):
    def test_native_station_manifest_requires_live_map_and_unique_scene_object(self):
        def waypoint(road,lane,s):
            return SimpleNamespace(road_id=road,lane_id=lane,s=s,lane_width=3.0,
                transform=SimpleNamespace(location=SimpleNamespace(
                    x=s if road==7 else 8,y=0 if road==7 else s)))
        world_map=SimpleNamespace(name='test-map',to_opendrive=lambda:'test-xodr',
                                  get_waypoint_xodr=waypoint)
        transform=SimpleNamespace(location=SimpleNamespace(x=4.0,y=2.0,z=0.0),
                                  rotation=SimpleNamespace(yaw=0.0))
        scene=SimpleNamespace(id=73,name='StationCandidate',type='Buildings',transform=transform)
        world=SimpleNamespace(get_environment_objects=lambda:[scene])
        survey={key:SURVEY[key] for key in ('public_before','public_at','public_after','driveway_at')}
        survey['routes']={branch:[ref(7,1,0),ref(7,1,8),ref(7,1,16)]
                          for branch in ('front_of_entrance','front_of_approach','remote_reference')}
        survey['routes']['through_driveway']=[ref(7,1,0),ref(8,2,6),ref(7,1,16)]
        manifest={'format':'worker-native-fire-station-survey-v1','map_name':'test-map',
                  'opendrive_sha256':hashlib.sha256(b'test-xodr').hexdigest(),
                  'reviewer':'synthetic-test-operator','evidence_reference':'synthetic-test-only',
                  'verified_fire_station':True,
                  'station_object':{'id':73,'name':'StationCandidate','type':'Buildings',
                                    'transform':{'x':4.0,'y':2.0,'z':0.0,'yaw':0.0}},
                  'station_survey':survey}
        raw=json.dumps(manifest).encode()
        verified,receipt=verify(world,world_map,manifest,hashlib.sha256(raw).hexdigest())
        self.assertEqual(verified['station_source']['kind'],'operator_survey')
        self.assertEqual(set(receipt['routes_verified']),set(survey['routes']))
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'operator.json';path.write_bytes(raw)
            with patch.dict(os.environ,{},clear=True):
                with self.assertRaisesRegex(ValueError,'CARLA_FIRE_STATION_SURVEY'):
                    load_and_verify(world,world_map,Path(temp))
            with patch.dict(os.environ,{'CARLA_FIRE_STATION_SURVEY':str(path)}):
                load_and_verify(world,world_map,Path(temp))
            self.assertEqual((Path(temp)/'station-survey-original.json').read_bytes(),raw)
        altered=dict(manifest,opendrive_sha256='0'*64)
        with self.assertRaisesRegex(ValueError,'OpenDRIVE'):
            verify(world,world_map,altered,hashlib.sha256(raw).hexdigest())
        absent=SimpleNamespace(get_environment_objects=lambda:[])
        with self.assertRaisesRegex(ValueError,'absent or ambiguous'):
            verify(absent,world_map,manifest,hashlib.sha256(raw).hexdigest())
        stale=dict(manifest,station_object=dict(manifest['station_object'],
                       transform={'x':40.0,'y':2.0,'z':0.0,'yaw':0.0}))
        with self.assertRaisesRegex(ValueError,'transform changed'):
            verify(world,world_map,stale,hashlib.sha256(raw).hexdigest())


if __name__=='__main__':unittest.main()
