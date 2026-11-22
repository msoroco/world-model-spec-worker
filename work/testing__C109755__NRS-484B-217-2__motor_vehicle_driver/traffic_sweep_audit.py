"""Independent source-bound audit of paired physical traffic challenges."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from traffic_sweep import CHANGES,select


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def one(record):
    attempt=Path(record['attempt']);saved_path=Path(record['saved_result'])
    seal=read(attempt/'capture-seal.json');acquisition=read(attempt/'acquisition.json')
    for name in ('turn-history.jsonl','zone-context.json','traffic-policy.json'):
        path=attempt/name
        if seal.get('sources',{}).get(name)!=sha(path) or \
           acquisition.get(name,{}).get('kind')!='original_native' or \
           acquisition[name].get('sha256')!=sha(path):
            raise ValueError('sweep original source missing or stale: '+name)
    policy=read(attempt/'traffic-policy.json');scene=read(attempt/'scene.json')
    _,expected,_=select(scene,policy.get('variant_id'))
    if policy!=expected:
        raise ValueError('sweep policy differs from declared one-factor plan')
    zone=read(attempt/'zone-context.json')
    if zone.get('traffic_sweep_variant_id')!=policy['variant_id'] or \
       zone.get('traffic_policy_sha256')!=sha(attempt/'traffic-policy.json') or \
       not zone.get('authority_source_sha256'):
        raise ValueError('sweep zone or policy source binding absent')
    saved=read(saved_path)
    if saved.get('case_id')!=scene['case_id'] or not all(saved.get(key) is True for key in
            ('setup_confirmed','behavior_attempted','maneuver_completed')):
        raise ValueError('sweep saved case or physical completion absent')
    measured=saved.get('measured_values',{})
    if measured.get('turn_history_sha256')!=sha(attempt/'turn-history.jsonl') or \
       measured.get('zone_context_sha256')!=sha(attempt/'zone-context.json'):
        raise ValueError('sweep saved measurement source hashes differ')
    history=rows(attempt/'turn-history.jsonl')
    if len(history)<3 or any(a['frame']>=b['frame'] or a['time_s']>=b['time_s']
                             for a,b in zip(history,history[1:])):
        raise ValueError('sweep original frame order invalid')
    stripe=zone['stripe_y_m'];crossing=None
    for index in range(1,len(history)):
        previous=max(v[1] for v in history[index-1]['ego_body_vertices_m'])
        current=max(v[1] for v in history[index]['ego_body_vertices_m'])
        if previous<stripe<=current:
            crossing=index;break
    if crossing is None:raise ValueError('sweep stripe crossing unobserved')
    time=history[crossing]['time_s'];before=[r for r in history if time-2<=r['time_s']<time]
    after=[r for r in history if time<=r['time_s']<=time+2]
    window=before+after
    if not before or not after or history[0]['time_s']>time-2 or \
       history[-1]['time_s']<time+2 or any(b['time_s']-a['time_s']>.1
                                            for a,b in zip(window,window[1:])):
        raise ValueError('sweep response window lacks complete original samples')
    saved_window=measured.get('traffic_response_window',{})
    if saved_window.get('full_window_observed') is not True or \
       saved_window.get('pre_sample_count')!=len(before) or \
       saved_window.get('crossing_and_post_sample_count')!=len(after):
        raise ValueError('sweep saved response window differs from original coverage')
    expected_signal='__signaled_' in scene['case_id']
    if scene.get('signal_enabled') is not expected_signal or \
       bool(history[crossing]['left_signal']) != expected_signal:
        raise ValueError('sweep signal policy differs at crossing')
    changes={}
    for role in ('oncoming','following'):
        if any(row.get('traffic_command_velocity_x_mps',{}).get(role)!=policy[role+'_velocity_x_mps']
               for row in history):
            raise ValueError('sweep traffic command differs from policy')
        def values(part):
            speeds=[];gaps=[]
            for row in part:
                vector=row[role+'_velocity_xy_mps'];gap=row[role+'_body_gap_m']
                if len(vector)!=2 or not all(math.isfinite(v) for v in vector) or \
                   not math.isfinite(gap) or gap<0:
                    raise ValueError('sweep participant velocity or gap invalid')
                speeds.append(math.hypot(*vector));gaps.append(gap)
            return speeds,gaps
        speeds_before,gaps_before=values(before)
        speeds_after,gaps_after=values(after)
        recorded=saved_window.get('participants',{}).get(role,{})
        if recorded.get('before',{}).get('speed_samples_mps')!=speeds_before or \
           recorded.get('crossing_and_after',{}).get('speed_samples_mps')!=speeds_after or \
           recorded.get('before',{}).get('body_gap_samples_m')!=gaps_before or \
           recorded.get('crossing_and_after',{}).get('body_gap_samples_m')!=gaps_after:
            raise ValueError('sweep saved participant response differs from original samples')
        speed_change=sum(speeds_after)/len(speeds_after)-sum(speeds_before)/len(speeds_before)
        gap_change=min(gaps_after)-min(gaps_before)
        observed_speed=recorded.get('mean_speed_change_mps')
        observed_gap=recorded.get('minimum_gap_change_m')
        if type(observed_speed) not in (int,float) or type(observed_gap) not in (int,float) or \
           not math.isclose(observed_speed,speed_change,abs_tol=1e-8) or \
           not math.isclose(observed_gap,gap_change,abs_tol=1e-8):
            raise ValueError('sweep saved response changes differ from original samples')
        changes[role]={'mean_speed_change_mps':speed_change,
                       'minimum_gap_change_m':gap_change}
    fixed={key:value for key,value in scene.items() if key not in ('case_id','signal_enabled')}
    return {'case_id':scene['case_id'],'variant_id':policy['variant_id'],
            'fixed_scene':fixed,'authority_source_sha256':zone['authority_source_sha256'],
            'policy_sha256':sha(attempt/'traffic-policy.json'),'response':changes}


def audit(records):
    results=[one(record) for record in records]
    prefix=Path(__file__).resolve().parent.name
    cases={prefix+'__signaled_left_turn',prefix+'__unsignaled_left_turn'}
    expected={(variant,case) for variant in CHANGES for case in cases}
    observed={(item['variant_id'],item['case_id']) for item in results}
    if len(results)!=len(expected) or observed!=expected:
        raise ValueError('sweep omits or duplicates an exact variant/case pair')
    if len({json.dumps(item['fixed_scene'],sort_keys=True) for item in results})!=1 or \
       len({item['authority_source_sha256'] for item in results})!=1:
        raise ValueError('sweep fixed scene or authority source differs')
    for variant in CHANGES:
        pair=[item for item in results if item['variant_id']==variant]
        if pair[0]['policy_sha256']!=pair[1]['policy_sha256']:
            raise ValueError('sweep paired signal comparison changed traffic policy')
    return {'format':'c109755-independent-traffic-sweep-audit-v1','passed':True,
            'variant_pairs':len(CHANGES),'responses':results,'legal_verdict':None}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('inventory')
    args=parser.parse_args();print(json.dumps(audit(read(args.inventory)['records']),indent=2))


if __name__=='__main__':main()
