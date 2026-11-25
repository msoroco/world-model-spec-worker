import json
import shutil
import tempfile
import unittest
from pathlib import Path

from analysis import analyze
from overpass_source import CASES, FRAMES, sha
from test_overpass_source import ROOT, rows, scene, write_attempt


def analysis_attempt(root, variant):
    write_attempt(root, variant)
    for old, new in (('map.xodr','candidate-overpass.xodr'),
                     ('body.jsonl','body-history.jsonl'),
                     ('frames.jsonl','video_frames.jsonl')):
        (root/old).rename(root/new)
    original = rows(variant)
    mapping = [{'video_frame':i, 'carla_frame':r['frame'],
                'native_frame':r['frame'], 'time_s':r['time_s']}
               for i,r in enumerate(original)]
    (root/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in mapping))
    (root/'trace.jsonl').write_text(''.join(json.dumps({
        'frame':r['frame'],'time_s':r['time_s'],
        'position_m':r['pedestrian_xyz_m']})+'\n' for r in original))
    manifest = json.loads((root/'source-manifest.json').read_text())
    for key,new in (('map','candidate-overpass.xodr'),
                    ('body_history','body-history.jsonl'),
                    ('frame_map','video_frames.jsonl')):
        manifest[key] = {'path':new,'sha256':sha(root/new)}
    (root/'source-manifest.json').write_text(json.dumps(manifest))
    description = {'channels':[{'name':name,'unit':'structured'} for name in
                   ('crossing_order','roadway_vehicle_inventory',
                    'provided_overhead_crossing','designated_place_prohibition')],
                   'context_inputs':[]}
    config = {'law_id':'LVMC-11-30-060-B','cell_id':'C188132',
              'actor':'pedestrian','selected_case_id':scene(variant)['case_id'],
              'diagnostic_only':True,'recording_description':description,
              'physical_completion':{'criterion':'travel_progress',
                                     'motion_source':'body-history.jsonl',
                                     'position_key':'pedestrian_xyz_m',
                                     'minimum_progress_m':10.0,
                                     'minimum_samples':FRAMES,
                                     'context_sources':['reviewed-site.json']}}
    (root/'config.json').write_text(json.dumps(config))
    for name in ('overview','approach','reference_corner','driver_reference'):
        (root/(name+'.mkv')).write_text('synthetic analysis-only marker\n')


class AnalysisTests(unittest.TestCase):
    def test_saved_finalizer_measures_exact_sources_without_legal_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'attempt'
            analysis_attempt(root, CASES[0])
            report = analyze(root,root/'analysis-report.json')
            result = json.loads((root/'result.json').read_text())
            self.assertTrue(report['measurements']['crossing_order']['value'][
                'pedestrian_entered_after_vehicle_passed'])
            self.assertEqual(result['case_id'],scene(CASES[0])['case_id'])
            self.assertEqual(result['legal_judgment'],'unresolved')
            self.assertTrue(result['diagnostic_fixture'])
            self.assertEqual(len(list((root/'channels').glob('*.jsonl'))),4)

    def test_missing_source_and_stale_review_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'attempt'
            analysis_attempt(root, CASES[2])
            (root/'body-history.jsonl').unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source: body-history.jsonl'):
                analyze(root,root/'analysis-report.json')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'attempt'
            analysis_attempt(root, CASES[2])
            (root/'municipal-designation-source.txt').write_text('changed\n')
            with self.assertRaisesRegex(ValueError,'hash differs'):
                analyze(root,root/'analysis-report.json')


if __name__ == '__main__':
    unittest.main()
