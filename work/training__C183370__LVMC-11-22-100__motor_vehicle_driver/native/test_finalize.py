import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from finalize import build_result, derive_channels, finalize, measurement_records
from recording_contract import CHANNELS, config
from test_analyze import READBACK, source_rows

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.native_output import validate_result
from batch_pipeline.validation import recording_description
from worker_exchange.measurement_contract import validate as validate_measurements
from worker_exchange.measurement_contract import verify_report


def analysis():
    return {'case':'reference','source_hashes':{name:'a'*64 for name in
        ('native-actors.jsonl','video_frames.jsonl','live-readback.json')},
        'observations':{'source_frames':600,'source_elapsed_s':30.0,
            'pavement_footprint_contact_frames':[300],
            'pavement_footprint_contact_observed':True,
            'requested_footprint_contact_matched':True,
            'warning_person_present_near_pavement_frames':600}}


class FinalizeTest(unittest.TestCase):
    def test_native_result_matches_pinned_schema_without_acceptance(self):
        cfg=config('reference',600)
        recording_description(cfg['recording_description'])
        result=validate_result(build_result(cfg,analysis()))
        self.assertEqual(len(result['recording_evidence']),len(CHANNELS)+1)
        self.assertFalse(result['setup_confirmed'])
        self.assertFalse(result['maneuver_completed'])
        self.assertFalse(result['accepted'])

    def test_rejects_changed_case_binding(self):
        cfg=config('reference',600); cfg['case_id']='wrong'
        with self.assertRaisesRegex(ValueError,'recording contract'):
            build_result(cfg,analysis())

    def test_channels_derive_from_retained_rows(self):
        frames,actors=source_rows(2)
        for actor in actors:
            actor.update(ego_position_xyz_m=[-5,0,0],ego_yaw_deg=0,
                         ego_velocity_xyz_mps=[1,0,0],ego_speed_mps=1,
                         ego_road_id=8,ego_lane_id=1)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            (path/'video_frames.jsonl').write_text(''.join(__import__('json').dumps(x)+'\n' for x in frames))
            (path/'native-actors.jsonl').write_text(''.join(__import__('json').dumps(x)+'\n' for x in actors))
            (path/'live-readback.json').write_text(__import__('json').dumps(
                {'plan':dict(READBACK['plan'],map_name='surveyed-map'),
                 'pavement_road_id':8}))
            receipts=derive_channels(path,analysis())
            self.assertEqual(set(receipts),set(CHANNELS))
            self.assertEqual(len((path/'channels/ego_pose.jsonl').read_text().splitlines()),2)

    def test_selected_measurements_bind_actual_source_hashes(self):
        import hashlib,json
        folder=REPO/'work/training__C183370__LVMC-11-22-100__motor_vehicle_driver'
        plan=json.loads((folder/'case-plan.json').read_text())
        code=(folder/'native/finalize.py').read_text()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            data=analysis()
            for name in ('native-actors.jsonl','video_frames.jsonl','live-readback.json'):
                (path/name).write_text(name+'\n')
                data['source_hashes'][name]=hashlib.sha256((path/name).read_bytes()).hexdigest()
            report={'measurements':measurement_records(data)}
            for case in ('reference','contrast'):
                case_id=folder.name+'__'+case
                contract=json.loads((folder/'selected-measurement-contracts'/(
                    case+'.json')).read_text())
                validate_measurements(contract,plan['requirement_dispositions'],
                                      code,case_id)
                values=verify_report(contract,report,path)
                self.assertEqual(len(values),2)
                self.assertFalse(values['surveyed_pavement_contact']['value']['warning_act_verified'])

    def test_missing_selected_source_fails_before_finalization(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            (path/'native-actors.jsonl').write_text('')
            (path/'video_frames.jsonl').write_text('')
            with self.assertRaisesRegex(ValueError,'Missing required source: live-readback.json'):
                finalize(path,path/'analysis-report.json')


if __name__=='__main__':
    unittest.main()
