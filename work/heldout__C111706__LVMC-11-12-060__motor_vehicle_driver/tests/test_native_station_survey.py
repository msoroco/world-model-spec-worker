import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as S

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from native_station_survey import load_native_survey


class NativeSurveyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        material=b'{"source":"synthetic operator site review"}\n'
        (self.root/'source.json').write_bytes(material)
        self.manifest={'format':'worker-fire-station-native-survey-v1',
            'station_source':{'kind':'operator_survey','reviewer':'synthetic test reviewer',
                'asset_id':'environment-object:42','source_path':'source.json',
                'source_sha256':hashlib.sha256(material).hexdigest()},
            'map_name':'test-map','opendrive_sha256':hashlib.sha256(b'test-xodr').hexdigest(),
            'scene_object':{'id':42,'name':'test station frontage','type':'Buildings',
                            'location_m':[3.,2.,0.]}}
        for key in ('public_before','public_at','public_after','driveway_at'):
            self.manifest[key]={'road_id':7,'lane_id':1,'s':0}
        self.manifest['routes']={'front_entrance_turn':[]}
        self.manifest['other_route']=[]
        self.path=self.root/'manifest.json'
        self.world=S(get_map=lambda:S(name='test-map',to_opendrive=lambda:'test-xodr'),
            get_environment_objects=lambda:[S(id=42,name='test station frontage',
                type='Buildings',transform=S(location=S(x=3.,y=2.,z=0.)))])

    def save(self):self.path.write_text(json.dumps(self.manifest))

    def test_original_source_map_and_object_verified(self):
        self.save()
        survey,receipt,raw,material=load_native_survey(self.path,self.world)
        self.assertEqual(survey['station_source']['asset_id'],'environment-object:42')
        self.assertEqual(receipt['manifest_sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(receipt['source_material_sha256'],hashlib.sha256(material).hexdigest())
        self.assertFalse(receipt['physical_acceptance_claimed'])

    def test_missing_or_stale_sources_rejected(self):
        self.save()
        (self.root/'source.json').write_text('changed')
        with self.assertRaisesRegex(ValueError,'missing or changed'):
            load_native_survey(self.path,self.world)
        (self.root/'source.json').write_bytes(b'{"source":"synthetic operator site review"}\n')
        self.manifest['opendrive_sha256']='0'*64;self.save()
        with self.assertRaisesRegex(ValueError,'OpenDRIVE'):
            load_native_survey(self.path,self.world)

    def test_ambiguous_scene_object_rejected(self):
        self.save()
        item=self.world.get_environment_objects()[0]
        self.world.get_environment_objects=lambda:[item,item]
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            load_native_survey(self.path,self.world)


if __name__=='__main__':unittest.main()
