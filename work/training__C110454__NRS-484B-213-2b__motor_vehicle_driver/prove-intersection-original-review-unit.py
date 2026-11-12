"""Exercise original context-review schema for both selected intersection cases."""
import copy,hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from delivery_audit import CAMERAS, check_context_review, check_pixel_review

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def reject(call):
 try:call()
 except ValueError:return
 raise AssertionError('Damaged intersection review accepted')
rows=[]
for suffix in ('reference','contrast'):
 case=HERE.name+'__'+suffix;attempt=ROOT/'.runtime-work/c110454-update040-intersection-draft'/suffix/'primary/compatibility';survey=json.loads((attempt/'road_geometry.json').read_text())
 review={'format':'c110454-original-road-context-review-v1','case_id':case,'source_kind':'original_native_map_and_scene','reviewer':'CPU unit schema fixture','method':'source-bound schema exercise only','road_geometry_sha256':sha(attempt/'road_geometry.json'),'road_xodr_sha256':sha(attempt/'road.xodr'),'statutory_or_traversal_context_sha256':sha(attempt/'context.json'),'native_map_sha256':survey['native_map_sha256'],'legal_verdict_claimed':False,'designation_confirmed':True,'zone_kind':'intersection','observations':['surveyed two-way intersection shape; synthetic fixture'],'limitations':'No original Native map or physical designation observed','two_way_native_readback':True}
 check_context_review(review,attempt,case,diagnostic=False)
 damaged=copy.deepcopy(review);damaged['two_way_native_readback']=False;reject(lambda:check_context_review(damaged,attempt,case,diagnostic=False))
 damaged=copy.deepcopy(review);damaged['road_geometry_sha256']='0'*64;reject(lambda:check_context_review(damaged,attempt,case,diagnostic=False))
 damaged=copy.deepcopy(review);damaged['designation_confirmed']=False;reject(lambda:check_context_review(damaged,attempt,case,diagnostic=False))
 source={'video_frames.jsonl':sha(attempt/'video_frames.jsonl')}
 decoded={}
 views={}
 for index,camera in enumerate(CAMERAS):
  digest=sha(attempt/(camera+'.mkv'));source[camera+'.mkv']=digest
  receipt=json.loads((attempt/f'source-{index}.json').read_text())
  assert receipt['video_sha256']==digest and receipt['frames']==480
  decoded[digest]={'frames':480,'rgb_sequence_sha256':receipt['rgb_sequence_sha256']}
  views[camera]={'video_sha256':digest,'reviewed_frame_ids':list(range(480)),
                 'subjects_visible':['ego_body','roadway','intersection'] if index==0 else [],
                 'limitations':'CPU schema fixture; no original visual claim',
                 'rgb_sequence_sha256':receipt['rgb_sequence_sha256']}
 pixel={'format':'c110454-original-pixel-review-v1','case_id':case,'frames':480,
        'source_kind':'original_native_camera_pixels','reviewer':'CPU unit schema fixture',
        'method':'source-bound schema exercise only','frame_map_sha256':source['video_frames.jsonl'],
        'legal_verdict_claimed':False,'views':views}
 check_pixel_review(pixel,case,source,decoded,diagnostic=False)
 damaged=copy.deepcopy(pixel);damaged['views']['overview']['subjects_visible']=['roadway'];reject(lambda:check_pixel_review(damaged,case,source,decoded,diagnostic=False))
 damaged=copy.deepcopy(pixel);damaged['views']['overview']['rgb_sequence_sha256']='0'*64;reject(lambda:check_pixel_review(damaged,case,source,decoded,diagnostic=False))
 rows.append({'case_id':case,'context_schema_branch_passed':True,
              'pixel_schema_branch_passed':True,'damaged_rejected':5})
print(json.dumps({'format':'c110454-intersection-original-context-schema-unit-v1','cases':rows,'original_native_review_performed':False,'recordings_accepted':0}))
