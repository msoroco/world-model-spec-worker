"""Build exact unselected source-and-lane comparison bundles."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
REPO=HERE.parents[2]
ASSIGNMENT='training__C230247__NRS-484B-307-12a__motor_vehicle_driver'
RUNTIME_SHA=hashlib.sha256((REPO/'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest()
CAMERAS=[{'name':n,'width':w,'height':h} for n,w,h in (
    ('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720))]
entries=[]
for tag,lane in (('same_lane',-1),('other_lane',-2)):
    cid=ASSIGNMENT+'__probe_'+tag
    cfg={'case_id':cid,'selected_case_id':cid,'supported_case_ids':[cid],
         'law_id':'NRS-484B-307-12a','cell_id':'C230247','actor':'motor_vehicle_driver',
         'rate_hz':20,'duration_s':30,'cameras':CAMERAS,'required_atoms':[],
         'source_packets':[],'case':{'case_id':cid,'target_lane_id':lane},
         'status':'unselected_native_draft',
         'recording_description':{'channels':[{'name':'signal_indication','unit':'enum'},
                                              {'name':'signal_lane_id','unit':'map lane id'},
                                              {'name':'actor_body_vertices_m','unit':'meters'},
                                              {'name':'occupied_lane_id','unit':'map lane id'}],
                                  'limitations':['official device authority and actual green arrow display unverified',
                                                 'Native route, four-camera capture, and saved processing unfinished']}}
    files=[{'path':'runner.py','content':(HERE/'draft_runner.py').read_text()},
           {'path':'signal_source.py','content':(HERE/'signal_source.py').read_text()},
           {'path':'capture.py','content':(HERE/'capture.py').read_text()},
           {'path':'road.xodr','content':(HERE/'road.xodr').read_text()},
           {'path':'config.json','content':json.dumps(cfg,indent=2)+'\n'},
           {'path':'tests/test_draft.py','content':(HERE/'draft_test.py').read_text()}]
    proposal={'case_id':cid,'law_id':'NRS-484B-307-12a','cell_id':'C230247',
              'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
              'recording_description':cfg['recording_description'],'status':'draft_not_selected'}
    dest=ROOT/('draft-'+tag)
    dest.mkdir(exist_ok=True)
    cp=dest/'construction.json'
    cp.write_text(json.dumps(proposal,indent=2)+'\n')
    entries.append({'case_id':cid,'id':'primary','kind':'draft_not_selected',
                    'construction':str(cp.relative_to(ROOT)),
                    'construction_sha256':hashlib.sha256(cp.read_bytes()).hexdigest(),
                    'candidate_risk':{'status':'physical','reason':'Native lane occupancy and green arrow display unverified'},
                    'candidates':[]})
manifest={'format':'worker-unselected-draft-construction-manifest-v1',
          'assignment_id':ASSIGNMENT,'runtime_manifest_sha256':RUNTIME_SHA,
          'status':'draft_not_selected','cases':entries}
(ROOT/'draft-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'runtime_sha256':RUNTIME_SHA,'cases':entries},sort_keys=True))
