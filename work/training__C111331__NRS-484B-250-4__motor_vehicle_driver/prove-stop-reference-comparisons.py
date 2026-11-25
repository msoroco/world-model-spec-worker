"""Exercise original-shaped comparison predicates with labeled synthetic rows."""
import argparse
import json
from pathlib import Path
import shutil

from stop_reference_physical_audit import audit

ROOT=Path(__file__).resolve().parent
SCRATCH=ROOT.parents[1]/'.runtime-work/c111331-2504-stopref-physical-fixture'


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def write_rows(path,values):
    path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in values))


def construct(name,reference):
    source=ROOT/'precedence'/name/'sources';target=SCRATCH/name
    target.mkdir(parents=True,exist_ok=True)
    history=[json.loads(x) for x in (source/'vehicle-history.jsonl').read_text().splitlines()]
    config=json.loads(next(f['content'] for f in
        json.loads((ROOT/'precedence'/name/'primary/construction.json').read_text())['files']
        if f['path']=='config.json'))
    write(target/'config.json',config)
    shutil.copyfile(source/'road.xodr',target/'road.xodr')
    shutil.copyfile(source/'video_frames.jsonl',target/'video_frames.jsonl')
    write(target/'native-map-readback.json',{'source_kind':'original_native',
        'incoming':{'250':{'reference_x_m':reference},
                    '253':{'reference_y_m':reference}},
        'synthetic_fixture':True})
    actors=[];signals=[]
    for i,row in enumerate(history):
        x,y=row['ego_center_xy_m'];ox,oy=row['other_center_xy_m']
        def box(cx,cy):return [[cx+dx,cy+dy,z] for dx in (-2,2) for dy in (-.9,.9) for z in (0,1.5)]
        speed=0 if i and row['ego_center_xy_m']==history[i-1]['ego_center_xy_m'] else 2.0
        other_speed=0 if i and row['other_center_xy_m']==history[i-1]['other_center_xy_m'] else 4.0
        actors.append({'frame':i,'native_frame':i,'time_s':i/20,
            'source_kind':'original_native','synthetic_fixture':True,
            'ego':{'body_native_xyz_m':box(x,y),'center_native_xyz_m':[x,y,.5],'speed_mps':speed},
            'other':{'body_native_xyz_m':box(ox,oy),'center_native_xyz_m':[ox,oy,.5],'speed_mps':other_speed}})
        signals.append({'frame':i,'time_s':i/20,'source_kind':'original_native',
            'synthetic_fixture':True,'governing_heads':{
                '250:-1':{'state':'Off','light_box_count':1},
                '253:-1':{'state':'Off','light_box_count':1}}})
    write_rows(target/'native-raw-actors.jsonl',actors)
    write_rows(target/'native-signal-readback.jsonl',signals)
    write(target/'human-review.json',{'findings':{'view_opening_visible':True},
        'synthetic_fixture':True})
    return target


def main(negative=False):
    if SCRATCH.exists():shutil.rmtree(SCRATCH)
    results={}
    for kind,stop,no_stop,reference in (
        ('crosswalk','crosswalk_stop','crosswalk_no_stop',-23.0),
        ('visible_point','visible_point_stop','visible_point_no_stop',-21.0)):
        paths=[construct(stop,reference),construct(no_stop,reference)]
        positive=audit(kind,*paths)
        positive['synthetic_fixture']=True
        positive['original_native_observed']=False
        results[kind]=positive
        missing=paths[0]/'native-signal-readback.jsonl'
        missing.unlink()
        if negative:audit(kind,*paths)
        try:audit(kind,*paths)
        except ValueError as exc:
            if 'Missing required original source' not in str(exc):raise
        else:raise AssertionError('Missing original signal source accepted')
        write_rows(missing,[])  # Retain the negative alteration only in scratch.
    return {'format':'c111331-stop-reference-physical-fixture-proof-v1',
            'passed':True,'original_native_observed':False,'comparisons':results,
            'negative_missing_original_source_rejected':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--negative',action='store_true')
    args=parser.parse_args()
    print(json.dumps(main(args.negative),indent=2,sort_keys=True))
