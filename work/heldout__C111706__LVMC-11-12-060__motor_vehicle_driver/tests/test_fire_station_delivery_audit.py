import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import fire_station_delivery_audit as delivery
from fire_station_finalizer import analyze, build_result


class DeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        diagnostic=json.loads((ROOT/'diagnostic-front_entrance_turn.json').read_text())
        for name in delivery.SOURCES:
            (self.root/name).write_text(diagnostic['files'][name])
        (self.root/'config.json').write_bytes((ROOT/'config.json').read_bytes())
        (self.root/'fixture-provenance.json').write_text('{"kind":"synthetic_diagnostic"}\n')
        for name in delivery.CAMERAS:
            (self.root/(name+'.mkv')).write_bytes(b'synthetic camera source')
        (self.root/'raw.mkv').write_bytes(b'synthetic composed video')
        self.case=json.loads((self.root/'config.json').read_text())['selected_case_id']
        self.finalize()

    def finalize(self):
        report=analyze(self.root)
        result=build_result(self.root,report)
        (self.root/'analysis-report.json').write_text(json.dumps(report))
        (self.root/'result.json').write_text(json.dumps(result))

    def fake_decode(self,path,frames,*,mapping_sha256,receipt):
        if not Path(path).is_file():raise FileNotFoundError(path)
        self.assertEqual(frames,9)
        self.assertEqual(mapping_sha256,delivery.digest(self.root/'video_frames.jsonl'))
        Path(receipt).write_text('{"fixture_decode":true}\n')
        return {'auditor_sha256':'fixture-media-auditor',
                'video_sha256':delivery.digest(path)}

    def test_fixture_source_join_and_stale_original_rejection(self):
        with patch.object(delivery.media,'audit',self.fake_decode):
            observed=delivery.audit(self.case,self.root,diagnostic_fixture=True)
        self.assertTrue(observed['checks']['all_participants'])
        self.assertFalse(observed['checks']['actual_pixels'])
        path=self.root/'other_original.jsonl'
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        rows[1]['center_xy'][0]+=1
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        with self.assertRaisesRegex(ValueError,'measurement differs'):
            delivery.audit(self.case,self.root,diagnostic_fixture=True)

    def test_native_review_branch_requires_current_pixels_and_station(self):
        config_path=self.root/'config.json';config=json.loads(config_path.read_text())
        survey_path=self.root/'station_survey.json';survey=json.loads(survey_path.read_text())
        source={'kind':'operator_survey','asset_id':'source-backed-test-station',
                'source_sha256':'4'*64}
        config['station_source']=source;config['station_survey']['station_source']=source
        survey['station_source']=source
        config_path.write_text(json.dumps(config));survey_path.write_text(json.dumps(survey))
        (self.root/'fixture-provenance.json').unlink()
        (self.root/'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind':'native','diagnostic_fixture':False}))
        for name in ('analysis-report.json','result.json','station_context-recorded.json'):
            (self.root/name).unlink()
        for channel in config['case']['recording_description']['channels']:
            (self.root/(channel['name']+'.jsonl')).unlink()
        self.finalize()
        seal_path=self.root/'capture-seal.json'
        sources={name:delivery.digest(self.root/name) for name in delivery.SOURCES}
        seal_path.write_text(json.dumps({'provenance_kind':'native',
                                         'restoration':{'restored':True},
                                         'sources':sources}))
        (self.root/'native-exit.json').write_text(json.dumps({
            'event':'native_exit','capture_seal_sha256':delivery.digest(seal_path)}))
        review={'case_id':self.case,'reviewer':'synthetic unit reviewer',
                'original_sha256':sources,
                'visible':{label:{'camera':'overview','video_frame':1,
                                  'camera_sha256':delivery.digest(self.root/'overview.mkv'),
                                  'observed':True}
                           for label in ('subject_body','other_body','station_entrance','turn_area')},
                'physical':{'station_asset_reviewed':True,
                            'opposite_direction_turn_observed':True,
                            'other_vehicle_observed':True,'no_contact_observed':True}}
        review_path=self.root/'station-physical-pixel-review.json'
        review_path.write_text(json.dumps(review))
        with patch.object(delivery.media,'audit',self.fake_decode):
            observed=delivery.audit(self.case,self.root)
        self.assertTrue(observed['checks']['physical_completion'])
        (self.root/'fixture-provenance.json').write_text('{"kind":"synthetic_diagnostic"}')
        with patch.object(delivery.media,'audit',self.fake_decode):
            with self.assertRaisesRegex(ValueError,'rejects fixture provenance'):
                delivery.audit(self.case,self.root)
        (self.root/'fixture-provenance.json').unlink()
        review['visible']['station_entrance']['camera_sha256']='stale'
        review_path.write_text(json.dumps(review))
        with patch.object(delivery.media,'audit',self.fake_decode):
            with self.assertRaisesRegex(ValueError,'pixel review missing'):
                delivery.audit(self.case,self.root)


if __name__=='__main__':unittest.main()
