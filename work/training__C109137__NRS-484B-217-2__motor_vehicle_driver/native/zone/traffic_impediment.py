"""Controlled traffic-response request at an adjoining-highway zone crossing."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parents[1].name
CASES={'clear_traffic':False,'following_brake':True}
FRAMES=600
RATE=20
CROSS_FRAME=200

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def row(i,condition):
    t=i/RATE;brake=CASES[condition]
    following_speed=12 if not brake or i<CROSS_FRAME else max(4,12-8*(i-CROSS_FRAME)/20)
    # Request source geometry is authored, not observed car motion.
    ego_x=-50+5*t
    return {'case_id':BASE+'__traffic_'+condition,'frame':i,'time_s':t,
            'source_kind':'authored_native_request',
            'zone':{'kind':'no_passing','striping_x_m':0,'adjoining_highway_id':'adjacent_road_2',
                    'statutory_designation_verified':False},
            'ego':{'x_m':round(ego_x,5),'speed_mps':5,'left_indicator_observed_request':i>=120,
                   'crossing_marking':i==CROSS_FRAME,'destination':'adjacent_road_2'},
            'oncoming':{'actor_id':'oncoming_1','speed_mps':11,'brake_commanded':False,
                        'minimum_path_clearance_m':30},
            'following':{'actor_id':'following_1','speed_mps':round(following_speed,5),
                         'brake_commanded':brake and i>=CROSS_FRAME,
                         'minimum_path_clearance_m':20 if brake else 35},
            'original_native_observed':False,'legal_verdict':None}

def build(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);entries=[]
    for condition in CASES:
        p=out/(condition+'.jsonl');p.write_text(''.join(json.dumps(row(i,condition),sort_keys=True)+'\n' for i in range(FRAMES)))
        entries.append({'case_id':BASE+'__traffic_'+condition,'condition':condition,'path':p.name,'sha256':sha(p),'frames':FRAMES})
    return {'format':'c109137-traffic-impediment-request-v1','duration_s':30,'rate_hz':RATE,
            'entries':entries,'native_executed':False,'selected_delivery_claimed':False}

def meter(path):
    p=Path(path);rows=[json.loads(x) for x in p.read_text().splitlines()]
    if len(rows)!=FRAMES:raise ValueError('Incomplete 600-frame source window')
    if len({r.get('case_id') for r in rows})!=1 or rows[0]['case_id'] not in [BASE+'__traffic_'+x for x in CASES]:raise ValueError('Case identity differs')
    if {r.get('source_kind') for r in rows}!={'authored_native_request'}:raise ValueError('Unsealed or forged provenance')
    for i,r in enumerate(rows):
        if r.get('frame')!=i or abs(r.get('time_s',-1)-i/RATE)>1e-6:raise ValueError('Frame/time join differs')
        z,e,o,f=(r.get(k,{}) for k in ('zone','ego','oncoming','following'))
        if z.get('kind')!='no_passing' or z.get('striping_x_m')!=0 or z.get('adjoining_highway_id')!='adjacent_road_2':raise ValueError('Zone/adjoining-highway source differs')
        if e.get('destination')!='adjacent_road_2' or e.get('crossing_marking')!=(i==CROSS_FRAME) or e.get('left_indicator_observed_request')!=(i>=120):raise ValueError('Signal/crossing source differs')
        if o.get('actor_id')!='oncoming_1' or f.get('actor_id')!='following_1':raise ValueError('Traffic actor source absent')
        if not all(isinstance(a.get('speed_mps'),(int,float)) for a in (e,o,f)):raise ValueError('Traffic velocity source absent')
        if not all(isinstance(a.get('minimum_path_clearance_m'),(int,float)) for a in (o,f)):raise ValueError('Traffic clearance source absent')
    before=sum(r['following']['speed_mps'] for r in rows[160:200])/40
    after=min(r['following']['speed_mps'] for r in rows[220:260])
    return {'format':'c109137-traffic-response-meter-v1','case_id':rows[0]['case_id'],'source_sha256':sha(p),
            'frames':FRAMES,'crossing_frame':CROSS_FRAME,'following_speed_drop_mps':round(before-after,5),
            'following_brake_commanded_at_crossing':rows[CROSS_FRAME]['following']['brake_commanded'],
            'minimum_oncoming_clearance_m':min(r['oncoming']['minimum_path_clearance_m'] for r in rows),
            'minimum_following_clearance_m':min(r['following']['minimum_path_clearance_m'] for r in rows),
            'impediment_legally_determined':False,'physical_completion_claimed':False,'legal_verdict_claimed':False}

def prove(out):
    manifest=build(out);out=Path(out);meters={e['condition']:meter(out/e['path']) for e in manifest['entries']}
    if meters['clear_traffic']['following_speed_drop_mps']!=0 or meters['following_brake']['following_speed_drop_mps']!=8:raise AssertionError('Traffic-response comparison differs')
    negatives={}
    for name,change,expected in (
        ('missing_traffic',lambda r:r[0]['following'].clear(),'Traffic actor source absent'),
        ('wrong_adjoining',lambda r:r[0]['zone'].update(adjoining_highway_id='unconnected'),'Zone/adjoining-highway source differs'),
        ('missing_clearance',lambda r:r[0]['oncoming'].pop('minimum_path_clearance_m'),'Traffic clearance source absent'),
        ('forged_source',lambda r:r[0].update(source_kind='original_native'),'Unsealed or forged provenance')):
        rows=[json.loads(x) for x in (out/'following_brake.jsonl').read_text().splitlines()]
        change(rows);p=out/(name+'.jsonl');p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
        try:meter(p)
        except ValueError as exc:
            if str(exc)!=expected:raise
            negatives[name]=expected
        else:raise AssertionError('Negative accepted: '+name)
    return {'format':'c109137-traffic-impediment-proof-v1','manifest':manifest,'meters':meters,
            'negative_rejections':negatives,'native_executed':False,'selected_delivery_claimed':False}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=('build','meter','prove'));ap.add_argument('--output');ap.add_argument('--source');a=ap.parse_args()
    print(json.dumps(meter(a.source) if a.command=='meter' else build(a.output) if a.command=='build' else prove(a.output),indent=2,sort_keys=True))
