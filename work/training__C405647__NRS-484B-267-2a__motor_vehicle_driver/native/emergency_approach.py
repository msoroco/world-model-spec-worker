"""Exact 30-second emergency-vehicle approach requests and diagnostic meter."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent.name + '__selected_d6045110__condition_'
CASES = {'a': 'reduce_speed', 'b': 'maintain_speed'}
FRAMES = 600
RATE = 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def row(frame, suffix):
    t = frame / RATE
    if suffix == 'a':
        speed = 14 if t < 8 else max(7, 14 - 3.5*(t-8))
        x = -100 + 14*min(t,8) + (14*(t-8)-1.75*(t-8)**2 if 8 <= t < 10 else 21 + 7*max(0,t-10)) if t >= 8 else -100+14*t
    else:
        speed, x = 14, -100+14*t
    return {'case_id': BASE+suffix, 'frame': frame, 'time_s': t,
            'source_kind': 'authored_native_request', 'ego': {'x_m': round(x,5), 'speed_mps': round(speed,5), 'approach_heading_deg': 0},
            'other_vehicle': {'x_m': round(100+2*t,5), 'speed_mps': 2, 'kind': 'authorized_emergency_vehicle',
                              'warning_lamps': 'qualifying_flashing_request', 'visible': True, 'heading_deg': 0},
            'officer_direction': None, 'posted_limit_mps': 15, 'weather': {'visibility_m': 200, 'wet_road': False},
            'original_native_observed': False, 'legal_verdict': None}


def build(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    entries=[]
    for suffix, condition in CASES.items():
        p=out/(condition+'.jsonl')
        p.write_text(''.join(json.dumps(row(i,suffix),sort_keys=True)+'\n' for i in range(FRAMES)))
        entries.append({'case_id':BASE+suffix,'condition':condition,'path':p.name,'sha256':sha(p),'frames':FRAMES})
    return {'format':'c405647-emergency-approach-request-v1','rate_hz':RATE,'duration_s':30,'entries':entries,'native_executed':False}


def meter(path):
    p=Path(path); rows=[json.loads(x) for x in p.read_text().splitlines()]
    if len(rows)!=FRAMES: raise ValueError('Incomplete 600-frame source window')
    if len({r.get('case_id') for r in rows})!=1 or rows[0]['case_id'] not in [BASE+s for s in CASES]:
        raise ValueError('Exact case identity differs')
    if {r.get('source_kind') for r in rows}!={'authored_native_request'}:
        raise ValueError('Unsealed or forged source provenance')
    for i,r in enumerate(rows):
        if r.get('frame')!=i or abs(r.get('time_s',-1)-i/RATE)>1e-6:
            raise ValueError('Source frame/time join differs')
        e,o=r.get('ego',{}),r.get('other_vehicle',{})
        if o.get('kind')!='authorized_emergency_vehicle' or o.get('speed_mps',0)<=0 or o.get('visible') is not True:
            raise ValueError('Visible moving qualifying vehicle source absent')
        if o.get('warning_lamps')!='qualifying_flashing_request':
            raise ValueError('Qualifying flashing-lamp source absent')
        if r.get('officer_direction') is not None:
            raise ValueError('Officer exception is not fixed absent')
        if not isinstance(e.get('speed_mps'),(float,int)) or not isinstance(e.get('x_m'),(float,int)):
            raise ValueError('Ego transform/speed source absent')
        if r.get('posted_limit_mps')!=15 or r.get('weather')!={'visibility_m':200,'wet_road':False}:
            raise ValueError('Reasonable-speed context differs')
    before=sum(r['ego']['speed_mps'] for r in rows[0:120])/120
    after=sum(r['ego']['speed_mps'] for r in rows[240:280])/40
    if rows[0]['other_vehicle']['x_m']<=rows[0]['ego']['x_m']:
        raise ValueError('Subject is not approaching from behind')
    return {'format':'c405647-speed-diagnostic-v1','case_id':rows[0]['case_id'],'source_sha256':sha(p),
            'frames':FRAMES,'speed_before_mps':before,'speed_after_mps':after,'decrease_mps':round(before-after,5),
            'qualifying_vehicle_moving':True,'qualifying_lamp_observed':False,
            'reasonable_and_proper_legally_determined':False,'physical_completion_claimed':False,'legal_verdict_claimed':False}


def prove(out):
    manifest=build(out); out=Path(out)
    meters={e['condition']:meter(out/e['path']) for e in manifest['entries']}
    if meters['reduce_speed']['decrease_mps']<5 or meters['maintain_speed']['decrease_mps']!=0:
        raise AssertionError('Controlled speed reduction not distinguished')
    negatives={}
    for name,change,expected in (
        ('missing_lamps',lambda r:r[0]['other_vehicle'].update(warning_lamps=None),'Qualifying flashing-lamp source absent'),
        ('stationary_vehicle',lambda r:r[0]['other_vehicle'].update(speed_mps=0),'Visible moving qualifying vehicle source absent'),
        ('officer_exception',lambda r:r[0].update(officer_direction='continue'),'Officer exception is not fixed absent'),
        ('forged_source',lambda r:r[0].update(source_kind='original_native'),'Unsealed or forged source provenance')):
        rows=[json.loads(x) for x in (out/'reduce_speed.jsonl').read_text().splitlines()]
        change(rows);p=out/(name+'.jsonl');p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
        try: meter(p)
        except ValueError as exc:
            if str(exc)!=expected:raise
            negatives[name]=expected
        else: raise AssertionError('Negative accepted: '+name)
    return {'format':'c405647-emergency-approach-proof-v1','manifest':manifest,'meters':meters,
            'negative_rejections':negatives,'native_executed':False,'legal_verdict_claimed':False}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=('build','meter','prove'));ap.add_argument('--output');ap.add_argument('--source')
    a=ap.parse_args();print(json.dumps(meter(a.source) if a.command=='meter' else build(a.output) if a.command=='build' else prove(a.output),indent=2,sort_keys=True))
