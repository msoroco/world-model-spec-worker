"""Synthetic CPU branch dispatch, continuous occupancy and altered-source proof."""
import json
from pathlib import Path
import tempfile

from qualifying_lane import LAW_PATHS, measure, sha

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def fixture(folder,case_id,right_only,approach_lane):
    folder.mkdir(parents=True)
    laws={}
    for key,path in LAW_PATHS.items():
        source=ROOT/path;data=json.loads(source.read_text())
        laws[key]={'input_sha256':sha(source),
                   'law_sha256':data['local_snapshot']['law_sha256']}
    write(folder/'law-bindings.json',laws)
    write(folder/'lane-design.json',{
        'case_id':case_id,'source_kind':'synthetic_cpu',
        'design_source':'native_map_survey',
        'single_right_only_turn_lane':right_only,
        'designated_turn_lane_id':-2 if right_only else None,
        'rightmost_lane_id':-1,'turn_connector_lane_id':-1,
        'physical_design_verified':False})
    with (folder/'actor-lane-sources.jsonl').open('x') as out:
        for i in range(600):
            phase='approach' if i<250 else 'turn' if i<450 else 'post_turn'
            row={'case_id':case_id,'frame':i,'time_s':i/20,
                 'phase':phase,'road_id':1 if phase=='approach' else 4,
                 'lane_id':approach_lane if phase=='approach' else -1}
            out.write(json.dumps(row,sort_keys=True)+'\n')


def prove():
    scratch=ROOT/'.runtime-work/c382355-400-1'
    scratch.mkdir(parents=True,exist_ok=True)
    entries=[];negatives=[]
    with tempfile.TemporaryDirectory(dir=scratch) as tmp:
        for name,right_only,lane,expected in (
            ('right_only_match',True,-2,1.0),
            ('right_only_other_lane',True,-1,0.0),
            ('extreme_right_match',False,-1,1.0),
            ('extreme_right_other_lane',False,-2,0.0)):
            folder=Path(tmp)/name
            case_id=CASE.name+'__'+name
            fixture(folder,case_id,right_only,lane)
            result=measure(ROOT,folder,case_id)
            assert result['required_approach_fraction']==expected
            assert result['required_turn_fraction']==1
            assert result['branch']==('single_right_only_turn_lane' if right_only else 'extreme_right_lane')
            assert not result['native_design_physically_verified'] and result['legal_verdict'] is None
            entries.append({'name':name,'measurement':result})
            source=folder/'actor-lane-sources.jsonl';original=source.read_text()
            source.write_text('\n'.join(original.splitlines()[:-1])+'\n')
            try:measure(ROOT,folder,case_id)
            except ValueError as error:negatives.append({'case':name,'mutation':'removed_actor_frame','error':str(error)})
            source.write_text(original)
            binding=folder/'law-bindings.json';original=binding.read_text()
            altered=json.loads(original);altered['223-4a']['law_sha256']='0'*64;write(binding,altered)
            try:measure(ROOT,folder,case_id)
            except ValueError as error:negatives.append({'case':name,'mutation':'changed_223_law_hash','error':str(error)})
            binding.write_text(original)
    assert len(negatives)==8
    receipt={'format':'c382355-400-1-qualifying-lane-cpu-proof-v1',
             'assignment_sha256':sha(ROOT/LAW_PATHS['400-1']),
             'module_sha256':sha(HERE/'qualifying_lane.py'),
             'entries':entries,'negative_controls':negatives,
             'passed':True,'source_kind':'synthetic_cpu',
             'original_native_observed':False,'delivery_ready':False}
    path=CASE/'qualifying-lane-proof.json';write(path,receipt)
    print(json.dumps({'passed':True,'branches':2,'diagnostics':len(entries),
                      'negative_controls':len(negatives),'receipt_sha256':sha(path)}))


if __name__=='__main__':prove()
