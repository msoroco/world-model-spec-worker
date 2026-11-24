"""Officer-direction exception requests and source-shape diagnostic for C10389."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parents[1].name
CASES={'no_direction_stop':False,'officer_directed_proceed':True}
FRAMES=600
RATE=20
STATION=50.0

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def request_row(i,condition):
    t=i/RATE;directed=CASES[condition]
    if directed:x=-10+4*t;speed=4
    elif t<13.5:x=-10+4*t;speed=4
    else:x=44;speed=0
    return {'case_id':BASE+'__'+condition,'frame':i,'time_s':t,'source_kind':'authored_native_request',
            'ego':{'center_x_m':round(x,4),'front_x_m':round(x+2,4),'speed_mps':speed,'lane_id':-1},
            'device':{'kind':'stop_sign','landmark_id':'3891','station_x_m':STATION,'governs_lane_id':-1,
                      'official_placement_verified':False,'signal_specific_307_exception':False},
            'officer':{'present':directed,'direction':'proceed' if directed and t>=10 else None,
                       'visible_to_ego':directed and t>=10},
            'original_native_observed':False,'legal_verdict':None}

def build(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);entries=[]
    for condition in CASES:
        p=out/(condition+'.jsonl')
        p.write_text(''.join(json.dumps(request_row(i,condition),sort_keys=True)+'\n' for i in range(FRAMES)))
        entries.append({'condition':condition,'case_id':BASE+'__'+condition,'path':p.name,'sha256':sha(p),'frames':FRAMES})
    return {'format':'c10389-officer-exception-request-v1','rate_hz':RATE,'duration_s':30,
            'entries':entries,'native_executed':False,'selected_delivery_claimed':False}

def meter(path):
    p=Path(path);rows=[json.loads(x) for x in p.read_text().splitlines()]
    if len(rows)!=FRAMES:raise ValueError('Incomplete 600-frame source window')
    if len({r.get('case_id') for r in rows})!=1 or rows[0]['case_id'] not in [BASE+'__'+c for c in CASES]:raise ValueError('Case identity differs')
    if {r.get('source_kind') for r in rows}!={'authored_native_request'}:raise ValueError('Unsealed or forged provenance')
    for i,r in enumerate(rows):
        if r.get('frame')!=i or abs(r.get('time_s',-1)-i/RATE)>1e-6:raise ValueError('Frame/time join differs')
        d,e,o=r.get('device',{}),r.get('ego',{}),r.get('officer',{})
        if d.get('kind')!='stop_sign' or d.get('landmark_id')!='3891' or d.get('station_x_m')!=STATION or d.get('governs_lane_id')!=-1:raise ValueError('Governing stop device source differs')
        if d.get('signal_specific_307_exception') is not False:raise ValueError('Signal-specific exception context differs')
        if not isinstance(e.get('center_x_m'),(int,float)) or not isinstance(e.get('front_x_m'),(int,float)) or e.get('lane_id')!=-1 or abs(e['front_x_m']-e['center_x_m']-2)>1e-4:raise ValueError('Ego body source differs')
        if not isinstance(e.get('speed_mps'),(int,float)):raise ValueError('Ego velocity source absent')
        if o.get('present') not in (True,False) or o.get('visible_to_ego') not in (True,False):raise ValueError('Officer source absent')
        if o.get('direction') not in (None,'proceed'):raise ValueError('Officer direction differs')
    entry=next((r for r in rows if r['ego']['front_x_m']>=STATION),None)
    direction=entry and entry['officer']['direction']=='proceed' and entry['officer']['visible_to_ego']
    return {'format':'c10389-officer-exception-meter-v1','case_id':rows[0]['case_id'],
            'source_sha256':sha(p),'frames':FRAMES,'entry_frame':entry['frame'] if entry else None,
            'officer_proceed_visible_at_entry':bool(direction),
            'official_placement_observed':False,'police_authority_observed':False,
            'physical_completion_claimed':False,'legal_verdict_claimed':False}

def prove(out):
    manifest=build(out);out=Path(out)
    meters={e['condition']:meter(out/e['path']) for e in manifest['entries']}
    if meters['no_direction_stop']['entry_frame'] is not None or not meters['officer_directed_proceed']['officer_proceed_visible_at_entry']:raise AssertionError('Controlled direction response differs')
    negatives={}
    for name,change,expected in (
        ('missing_officer',lambda r:r[0]['officer'].clear(),'Officer source absent'),
        ('wrong_device',lambda r:r[0]['device'].update(kind='yield_sign'),'Governing stop device source differs'),
        ('signal_exception',lambda r:r[0]['device'].update(signal_specific_307_exception=True),'Signal-specific exception context differs'),
        ('forged_source',lambda r:r[0].update(source_kind='original_native'),'Unsealed or forged provenance')):
        rows=[json.loads(x) for x in (out/'officer_directed_proceed.jsonl').read_text().splitlines()]
        change(rows);p=out/(name+'.jsonl');p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
        try:meter(p)
        except ValueError as exc:
            if str(exc)!=expected:raise
            negatives[name]=expected
        else:raise AssertionError('Negative accepted: '+name)
    return {'format':'c10389-officer-exception-proof-v1','manifest':manifest,'meters':meters,
            'negative_rejections':negatives,'native_executed':False,'selected_delivery_claimed':False}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=('build','meter','prove'));ap.add_argument('--output');ap.add_argument('--source');a=ap.parse_args()
    print(json.dumps(meter(a.source) if a.command=='meter' else build(a.output) if a.command=='build' else prove(a.output),indent=2,sort_keys=True))
