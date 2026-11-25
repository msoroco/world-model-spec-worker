"""Thirty-second post-cycle yielding requests and source meter."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent.name
CASES={'wait_for_clearance':17,'enter_during_occupancy':13}
FRAMES=600
RATE=20

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def row(i,condition):
    t=i/RATE;enter=CASES[condition]
    # Front remains before the nearest-side crosswalk until the chosen release.
    front=-2 if t<enter else min(25,-2+4*(t-enter))
    occupied=12<=t<16
    return {'case_id':BASE+'__yield_'+condition,'frame':i,'time_s':t,
            'source_kind':'authored_native_request',
            'subject':{'kind':'motorcycle','front_x_m':round(front,4),'speed_mps':0 if t<enter else 4,
                       'stopped_before_crosswalk':t<enter,'movement':'straight'},
            'signal':{'circular_red':True,'green_arrow_direction':'left',
                      'complete_unchanged_cycles':min(2,int(t/4)),'failed_detection_proven':False},
            'crosswalk':{'near_edge_x_m':0,'nearest_side':True,
                         'pedestrian_lawfully_within':occupied},
            'intersection_traffic':{'lawful_actor_present':occupied,'conflict_region_occupied':occupied},
            'prohibiting_device_present':False,
            'original_native_observed':False,'legal_verdict':None}

def build(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);entries=[]
    for condition in CASES:
        p=out/(condition+'.jsonl');p.write_text(''.join(json.dumps(row(i,condition),sort_keys=True)+'\n' for i in range(FRAMES)))
        entries.append({'condition':condition,'case_id':BASE+'__yield_'+condition,'path':p.name,'sha256':sha(p),'frames':FRAMES})
    return {'format':'c111071-yield-request-v1','rate_hz':RATE,'duration_s':30,'entries':entries,
            'native_executed':False,'selected_delivery_claimed':False}

def meter(path):
    p=Path(path);rows=[json.loads(x) for x in p.read_text().splitlines()]
    if len(rows)!=FRAMES:raise ValueError('Incomplete 600-frame source window')
    if len({r.get('case_id') for r in rows})!=1 or rows[0]['case_id'] not in [BASE+'__yield_'+x for x in CASES]:raise ValueError('Case identity differs')
    if {r.get('source_kind') for r in rows}!={'authored_native_request'}:raise ValueError('Unsealed or forged provenance')
    for i,r in enumerate(rows):
        if r.get('frame')!=i or abs(r.get('time_s',-1)-i/RATE)>1e-6:raise ValueError('Frame/time join differs')
        s,g,c,v=(r.get(k,{}) for k in ('subject','signal','crosswalk','intersection_traffic'))
        if s.get('kind')!='motorcycle' or s.get('movement')!='straight' or not isinstance(s.get('front_x_m'),(int,float)):raise ValueError('Subject motion source differs')
        if g.get('circular_red') is not True or g.get('green_arrow_direction')!='left' or g.get('complete_unchanged_cycles')!=min(2,int(i/RATE/4)):raise ValueError('Two-cycle signal source differs')
        if c.get('near_edge_x_m')!=0 or c.get('nearest_side') is not True or not isinstance(c.get('pedestrian_lawfully_within'),bool):raise ValueError('Crosswalk/pedestrian source absent')
        if not isinstance(v.get('lawful_actor_present'),bool) or not isinstance(v.get('conflict_region_occupied'),bool):raise ValueError('Lawful traffic source absent')
        if r.get('prohibiting_device_present') is not False:raise ValueError('Prohibiting-device context differs')
    entry=next((r for r in rows if r['subject']['front_x_m']>=0),None)
    if entry is None:raise ValueError('No entry after wait')
    if entry['signal']['complete_unchanged_cycles']<2:raise ValueError('Entry before two complete cycles')
    return {'format':'c111071-yield-meter-v1','case_id':rows[0]['case_id'],'source_sha256':sha(p),
            'frames':FRAMES,'entry_frame':entry['frame'],
            'pedestrian_in_crosswalk_at_entry':entry['crosswalk']['pedestrian_lawfully_within'],
            'lawful_traffic_in_conflict_at_entry':entry['intersection_traffic']['conflict_region_occupied'],
            'nondetection_causation_proven':False,'physical_completion_claimed':False,'legal_verdict_claimed':False}

def prove(out):
    manifest=build(out);out=Path(out);meters={e['condition']:meter(out/e['path']) for e in manifest['entries']}
    if meters['wait_for_clearance']['pedestrian_in_crosswalk_at_entry'] or not meters['enter_during_occupancy']['pedestrian_in_crosswalk_at_entry']:raise AssertionError('Yield comparison not separated')
    negatives={}
    for name,change,expected in (
        ('missing_pedestrian',lambda r:r[0]['crosswalk'].pop('pedestrian_lawfully_within'),'Crosswalk/pedestrian source absent'),
        ('missing_traffic',lambda r:r[0]['intersection_traffic'].clear(),'Lawful traffic source absent'),
        ('wrong_arrow',lambda r:r[0]['signal'].update(green_arrow_direction='right'),'Two-cycle signal source differs'),
        ('prohibiting_device',lambda r:r[0].update(prohibiting_device_present=True),'Prohibiting-device context differs'),
        ('forged_source',lambda r:r[0].update(source_kind='original_native'),'Unsealed or forged provenance')):
        rows=[json.loads(x) for x in (out/'enter_during_occupancy.jsonl').read_text().splitlines()]
        change(rows);p=out/(name+'.jsonl');p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
        try:meter(p)
        except ValueError as exc:
            if str(exc)!=expected:raise
            negatives[name]=expected
        else:raise AssertionError('Negative accepted: '+name)
    return {'format':'c111071-yield-proof-v1','manifest':manifest,'meters':meters,
            'negative_rejections':negatives,'native_executed':False,'selected_delivery_claimed':False}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=('build','meter','prove'));ap.add_argument('--output');ap.add_argument('--source');a=ap.parse_args()
    print(json.dumps(meter(a.source) if a.command=='meter' else build(a.output) if a.command=='build' else prove(a.output),indent=2,sort_keys=True))
