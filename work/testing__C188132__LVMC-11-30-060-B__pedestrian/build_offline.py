"""Build exact inline construction drafts from the assignment-owned sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
VARIANTS = ('yield_before_vehicle', 'enter_ahead_of_vehicle', 'designated_prohibition')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = {'format':'worker-draft-offline-manifest',
                'assignment_id':ASSIGNMENT,'cases':[]}
    for variant in VARIANTS:
        scene_file = ROOT/('scene-'+variant+'.json')
        scene = json.loads(scene_file.read_text())
        case_id = scene['case_id']
        recording_description = {
            'channels':[{'name':name,'unit':unit,
                         'method':'source-bound saved original measurement',
                         'time_window':'entire 45 second crossing',
                         'sampling_rate_hz':20,
                         'reference_frame':'original Native frame and world XY',
                         'uncertainty':'physical structure and legal judgment pending'}
                        for name,unit in (
                ('crossing_order','structured'),
                ('roadway_vehicle_inventory','structured'),
                ('provided_overhead_crossing','structured'),
                ('designated_place_prohibition','boolean'))],
            'context_inputs':[],
            'limitations':['Original structure, accessible deck, pixels and legal judgment require independent local review']}
        config = {'law_id':'LVMC-11-30-060-B','cell_id':'C188132',
                  'actor':'pedestrian','selected_case_id':case_id,
                  'supported_case_ids':[ASSIGNMENT+'__'+v for v in VARIANTS],
                  'rate_hz':20,'duration_s':45.0,'required_atoms':[],
                  'source_packets':[], 'case':{'case_id':case_id,
                    'recording_description':recording_description},
                  'recording_description':recording_description,
                  'physical_completion':{'criterion':'travel_progress',
                      'motion_source':'body-history.jsonl',
                      'position_key':'pedestrian_xyz_m',
                      'minimum_progress_m':10.0,
                      'minimum_samples':900,
                      'direction_xy':[0,1],
                      'context_sources':['reviewed-site.json']},
                  'cameras':[{'name':name,'width':w,'height':h,'fps':20,
                              'fov_deg':90,'pose_strategy':'fixed_overpass_and_surface_road'}
                             for name,(w,h) in (('overview',(1920,1080)),
                                 ('approach',(1280,720)),('reference_corner',(1280,720)),
                                 ('driver_reference',(1280,720)))]}
        files = []
        sources = {'runner.py':'runner.py',
                   'overpass_source.py':'overpass_source.py',
                   'native_capture.py':'native_capture.py',
                   'media_audit.py':'media_audit.py',
                   'delivery_audit.py':'delivery_audit.py',
                   'site_review.py':'site_review.py',
                   'analysis.py':'analysis.py',
                   'walker_pipeline_capture.py':'walker_pipeline_capture.py',
                   'scene.json':scene_file.name,
                   'candidate-overpass.xodr':'candidate-overpass.xodr',
                   'road.xodr':'candidate-overpass.xodr'}
        for destination, source in sources.items():
            files.append({'path':destination,'source':'work/'+ASSIGNMENT+'/'+source,
                          'content':(ROOT/source).read_text()})
        files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
        unit = '''import json
import unittest
from pathlib import Path
from overpass_source import validate_case
from native_capture import CAMERA_SPECS, camera_placements

class ExactConstruction(unittest.TestCase):
    def test_exact_map_route_and_cameras(self):
        root=Path(__file__).resolve().parents[1]
        scene=json.loads((root/'scene.json').read_text())
        config=json.loads((root/'config.json').read_text())
        self.assertEqual(scene['case_id'],config['selected_case_id'])
        self.assertEqual(config['rate_hz'],20)
        self.assertEqual(config['duration_s'],45.0)
        self.assertEqual(set(camera_placements(scene)),set(CAMERA_SPECS))
        self.assertEqual(validate_case(scene,root/'candidate-overpass.xodr')['deck_z_m'],5)
'''
        files.append({'path':'tests/test_exact.py','content':unit})
        construction={'law_id':'LVMC-11-30-060-B','cell_id':'C188132',
                      'actor':'pedestrian','case_id':case_id,
                      'entrypoint':'runner.py','files':files,
                      'recording_description':recording_description}
        construction_path=ROOT/'cases'/variant/'construction.json'
        write(construction_path,construction)
        manifest['cases'].append({'case_id':case_id,
                'construction':'cases/'+variant+'/construction.json',
                'construction_sha256':sha(construction_path),
                'candidate_risk':{'status':'physical',
                    'reason':'Primary camera placement may occlude the reviewed deck or roadway subjects; alternate fixed viewpoints are preplanned.'},
                'candidates':[]})
    write(ROOT/'draft-offline-manifest.json',manifest)


if __name__ == '__main__':
    main()
