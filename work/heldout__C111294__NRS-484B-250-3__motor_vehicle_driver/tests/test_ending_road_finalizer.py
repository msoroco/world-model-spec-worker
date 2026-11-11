import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ending_road_finalizer import analyze, build_result


def square(x, y):
    return [[x-.4,y-.4],[x+.4,y-.4],[x+.4,y+.4],[x-.4,y+.4]]


class EndingRoadFinalizerTests(unittest.TestCase):
    def make_attempt(self, root):
        config = json.loads((ROOT/'config.json').read_text())
        (root/'config.json').write_text(json.dumps(config))
        topology = {'highway_identity_source':'Native OpenDRIVE road_id',
                    'junction_id':'42','subject_id':'1','other_id':'2',
                    'subject_approach_lane':'s0','other_approach_lane':'o0',
                    'conflict_polygon_xy':[[-1,-1],[1,-1],[1,1],[-1,1]],
                    'lanes':{
                        's0':{'highway_id':'road1','junction_id':None,'successors':['s1']},
                        's1':{'highway_id':'junction','junction_id':'42','successors':['s2']},
                        's2':{'highway_id':'road2','junction_id':None,'successors':[]},
                        'o0':{'highway_id':'road3','junction_id':None,'successors':['o1']},
                        'o1':{'highway_id':'junction','junction_id':'42','successors':['o2']},
                        'o2':{'highway_id':'road3','junction_id':None,'successors':[]}}}
        (root/'intersection_topology.json').write_text(json.dumps(topology))
        mapping, trace, participants = [], [], []
        for i in range(4):
            frame, time_s = 100+i, i*.05
            mapping.append({'video_frame':i,'carla_frame':frame,'time_s':time_s})
            trace.append({'frame':frame,'time_s':time_s})
            participants.append({'frame':frame,'time_s':time_s,
                'subject_id':'1','other_id':'2',
                'subject_corners':square([-4,-4,0,3][i],0),
                'other_corners':square([-4,0,3,4][i],0)})
        for name, rows in (('video_frames.jsonl',mapping),('trace.jsonl',trace),
                           ('intersection_participants.jsonl',participants)):
            (root/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))

    def test_original_join_and_missing_topology_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_attempt(root)
            report = analyze(root)
            result = build_result(root, report)
            self.assertEqual(report['case_id'], result['case_id'])
            self.assertTrue(result['measured_values']['intersection_observation']
                            ['subject_entered_after_other_last_conflict_frame'])
            self.assertTrue((root/'intersection_occupancy.jsonl').is_file())
            (root/'intersection_topology.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                analyze(root)

    def test_rejects_unjoined_original_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_attempt(root)
            rows = (root/'video_frames.jsonl').read_text().splitlines()
            item = json.loads(rows[1]); item['carla_frame'] += 1
            rows[1] = json.dumps(item)
            (root/'video_frames.jsonl').write_text('\n'.join(rows)+'\n')
            with self.assertRaisesRegex(ValueError, 'join failed'):
                analyze(root)


if __name__ == '__main__':
    unittest.main()
