"""Thirty-second turn-signal request and continuous-distance diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent.name+'__probe_'
ONSET={'a':220,'b':260}
FRAMES=600
RATE=20

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def row(i,suffix):
    # Straight 10 m/s approach; right course change starts at frame 300.
    return {'case_id':BASE+suffix,'frame':i,'time_s':i/RATE,'source_kind':'authored_native_request',
            'ego':{'path_length_m':round(i*0.5,5),'speed_mps':10,'heading_deg':0 if i<300 else 90,
                   'course_change_onset_frame':300},
            'right_indicator':{'commanded_on':i>=ONSET[suffix], 'observed_lamp_on':i>=ONSET[suffix]},
            'hand_signal':None,'district':'business','weather':{'precipitation':'clear'},
            'original_native_observed':False,'legal_verdict':None}

def build(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);entries=[]
    for suffix in ONSET:
        p=out/('condition_'+suffix+'.jsonl')
        p.write_text(''.join(json.dumps(row(i,suffix),sort_keys=True)+'\n' for i in range(FRAMES)))
        entries.append({'case_id':BASE+suffix,'path':p.name,'sha256':sha(p),'frames':FRAMES})
    return {'format':'c42387-turn-signal-request-v1','rate_hz':RATE,'duration_s':30,'entries':entries,'native_executed':False}

def meter(path):
    p=Path(path);rows=[json.loads(x) for x in p.read_text().splitlines()]
    if len(rows)!=FRAMES:raise ValueError('Incomplete 600-frame source window')
    if len({r.get('case_id') for r in rows})!=1 or rows[0]['case_id'] not in [BASE+x for x in ONSET]:raise ValueError('Exact case differs')
    if {r.get('source_kind') for r in rows}!={'authored_native_request'}:raise ValueError('Unsealed or forged provenance')
    for i,r in enumerate(rows):
        if r.get('frame')!=i or abs(r.get('time_s',-1)-i/RATE)>1e-6:raise ValueError('Frame/time join differs')
        e,ind=r.get('ego',{}),r.get('right_indicator',{})
        if e.get('path_length_m')!=round(i*0.5,5) or e.get('speed_mps')!=10:raise ValueError('Path/speed source differs')
        if r.get('district')!='business' or r.get('weather',{}).get('precipitation')!='rain':raise ValueError('District/weather source differs')
        if ind.get('observed_lamp_on')!=ind.get('commanded_on') or not isinstance(ind.get('observed_lamp_on'),bool):raise ValueError('Observed signal source absent')
        if e.get('course_change_onset_frame')!=300 or e.get('heading_deg')!=(0 if i<300 else 90):raise ValueError('Course-change source differs')
    first=next((i for i,r in enumerate(rows[:300]) if r['right_indicator']['observed_lamp_on']),None)
    if first is None:raise ValueError('No signal onset before turn')
    if not all(r['right_indicator']['observed_lamp_on'] for r in rows[first:301]):raise ValueError('Signal not continuous to turn')
    dist=rows[300]['ego']['path_length_m']-rows[first]['ego']['path_length_m']
    return {'format':'c42387-signal-distance-meter-v1','case_id':rows[0]['case_id'],'source_sha256':sha(p),
            'frames':FRAMES,'signal_onset_frame':first,'course_change_frame':300,'continuous_signal_distance_m':dist,
            'business_district_100ft_distance_met_in_request':dist>=30.48,'weather_exception_applied':False,
            'physical_completion_claimed':False,'legal_verdict_claimed':False}

def prove(out):
    manifest=build(out);out=Path(out)
    meters={x['case_id']:meter(out/x['path']) for x in manifest['entries']}
    if [meters[BASE+s]['business_district_100ft_distance_met_in_request'] for s in ('a','b')]!=[True,False]:raise AssertionError('Comparison not separated')
    negatives={}
    for name,change,expected in (
        ('lamp_gap',lambda r:r[250]['right_indicator'].update(observed_lamp_on=False,commanded_on=False),'Signal not continuous to turn'),
        ('missing_lamp',lambda r:r[0]['right_indicator'].clear(),'Observed signal source absent'),
        ('wrong_district',lambda r:r[0].update(district='other'),'District/weather source differs'),
        ('forged_source',lambda r:r[0].update(source_kind='original_native'),'Unsealed or forged provenance')):
        rows=[json.loads(x) for x in (out/'condition_a.jsonl').read_text().splitlines()]
        change(rows);p=out/(name+'.jsonl');p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
        try:meter(p)
        except ValueError as exc:
            if str(exc)!=expected:raise
            negatives[name]=expected
        else:raise AssertionError('Negative accepted: '+name)
    return {'format':'c42387-signal-distance-proof-v1','manifest':manifest,'meters':meters,
            'negative_rejections':negatives,'native_executed':False,'legal_verdict_claimed':False}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=('build','meter','prove'));ap.add_argument('--output');ap.add_argument('--source');a=ap.parse_args()
    print(json.dumps(meter(a.source) if a.command=='meter' else build(a.output) if a.command=='build' else prove(a.output),indent=2,sort_keys=True))
