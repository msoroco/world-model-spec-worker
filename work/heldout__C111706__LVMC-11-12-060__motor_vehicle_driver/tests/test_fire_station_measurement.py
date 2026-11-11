import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fire_station_measurement import measure
from fire_station_finalizer import analyze, build_result


def body(x, y, half=0.4):
    return [[x-half,y-half],[x+half,y-half],
            [x+half,y+half],[x-half,y+half]]


class FireStationOriginalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_sources(self, *, reverse=False, driveway=False, remote=False):
        def wp(x, y, road=7, lane=1):
            return {'xy': [x,y], 'road_id': road, 'lane_id': lane,
                    'lane_width': 3.0}
        survey = {
            'station_source': {'kind':'operator_survey','asset_id':'fixture-station',
                               'source_sha256':'1'*64},
            'public_before':wp(8 if reverse else -8,0),
            'public_at':wp(0,0),
            'public_after':wp(-8 if reverse else 8,0),
            'driveway_at':wp(0,6,8,2),
        }
        (self.root/'station_survey.json').write_text(json.dumps(survey))
        xs = ([20,18,20] if remote else [5,0,5]) if reverse else (
            [-20,-18,-20] if remote else [-5,0,-5])
        ys = [0,3,0] if driveway else [0,0,0]
        headings = [180,270,360] if reverse else [0,90,180]
        a,b,mapping,trace=[],[],[],[]
        for index in range(3):
            a.append({'frame':100+index,'time_s':index*.05,
                      'native_actor_id':1,'center_xy':[xs[index],ys[index]],
                      'body_corners_xy':body(xs[index],ys[index],1.0),
                      'heading_deg':headings[index],
                      'road_id':8 if driveway and index==1 else 7,
                      'lane_id':2 if driveway and index==1 else 1})
            b.append({'frame':100+index,'time_s':index*.05,
                      'native_actor_id':2,'center_xy':[12,3],
                      'body_corners_xy':body(12,3),
                      'heading_deg':180,'road_id':7,'lane_id':-1})
            mapping.append({'video_frame':index,'carla_frame':100+index,'time_s':index*.05})
            trace.append({'frame':100+index,'time_s':index*.05})
        for name,rows in zip(('subject_original.jsonl','other_original.jsonl',
                              'video_frames.jsonl','trace.jsonl'),
                             (a,b,mapping,trace)):
            (self.root/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))

    def test_both_approaches_and_distinct_driveway_use(self):
        self.write_sources()
        east = measure(self.root)
        self.assertTrue(east['path']['reversal_observed'])
        self.assertTrue(east['path']['body_entrance_overlap_frames'])
        self.assertFalse(east['path']['entered_driveway'])
        self.assertGreater(east['other_vehicle_min_ground_body_clearance_m'], 0)
        self.write_sources(reverse=True, driveway=True)
        west = measure(self.root)
        self.assertTrue(west['path']['entered_driveway'])
        self.assertTrue(west['path']['body_entrance_overlap_frames'])
        self.assertEqual(west['station_identity'], 'unreviewed')
        self.assertEqual(west['turning_purpose'], 'unreviewed')
        self.assertEqual(len(west['source_refs']), 5)

    def test_remote_reference_and_missing_original_rejected(self):
        self.write_sources(remote=True)
        remote = measure(self.root)
        self.assertFalse(remote['path']['body_entrance_overlap_frames'])
        self.assertFalse(remote['path']['entered_driveway'])
        (self.root/'other_original.jsonl').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing required source'):
            measure(self.root)

    def test_frame_join_and_station_geometry_rejected(self):
        self.write_sources()
        path = self.root/'other_original.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[1]['frame'] += 1
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        with self.assertRaisesRegex(ValueError, 'frame/time join'):
            measure(self.root)
        self.write_sources()
        path = self.root/'station_survey.json'
        survey = json.loads(path.read_text())
        survey['driveway_at']['xy'] = [6,0]
        path.write_text(json.dumps(survey))
        with self.assertRaisesRegex(ValueError, 'physical branch angle'):
            measure(self.root)

    def test_saved_finalizer_uses_originals_and_rejects_missing_source(self):
        self.write_sources(driveway=True)
        survey = json.loads((self.root/'station_survey.json').read_text())
        names = ('reversal_heading_deg','entrance_overlap_frames',
                 'approach_overlap_frames','driveway_lane_frames',
                 'other_body_clearance_m','subject_path_length_m')
        config = {'law_id':'LVMC-11-12-060','cell_id':'C111706',
                  'actor':'motor_vehicle_driver',
                  'selected_case_id':'heldout__C111706__LVMC-11-12-060__motor_vehicle_driver__driveway_use_turn',
                  'station_source':survey['station_source'],
                  'case':{'recording_description':{'channels':[
                      {'name':name,'unit':'measured','method':'original source join'}
                      for name in names]}}}
        (self.root/'config.json').write_text(json.dumps(config))
        report = analyze(self.root)
        result = build_result(self.root,report)
        self.assertEqual(len(result['recording_evidence']),7)
        self.assertEqual(result['realized_observables']['driveway_lane_frames']['value'],1)
        self.assertFalse(result['physical_acceptance_claimed'])
        with self.assertRaisesRegex(ValueError,'Retain prior derived'):
            analyze(self.root)
        (self.root/'other_original.jsonl').unlink()
        with self.assertRaisesRegex(ValueError,'Missing required source'):
            measure(self.root)


if __name__ == '__main__':
    unittest.main()
