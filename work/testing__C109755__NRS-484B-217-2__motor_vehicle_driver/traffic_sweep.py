"""Controlled physical challenges for traffic response; no legal threshold."""
import hashlib
import json
import math


BASE={'oncoming_start_x_m':40.0,'following_start_x_m':-135.0,
      'oncoming_velocity_x_mps':-2.0,'following_velocity_x_mps':2.0}
CHANGES={
    'baseline':{},
    'oncoming_near':{'oncoming_start_x_m':20.0},
    'oncoming_far':{'oncoming_start_x_m':60.0},
    'oncoming_slower':{'oncoming_velocity_x_mps':-1.0},
    'oncoming_faster':{'oncoming_velocity_x_mps':-3.0},
    'following_near':{'following_start_x_m':-125.0},
    'following_far':{'following_start_x_m':-145.0},
    'following_slower':{'following_velocity_x_mps':1.0},
    'following_faster':{'following_velocity_x_mps':3.0},
}


def select(scene,variant_id):
    """Change one traffic input while retaining every other authored condition."""
    if variant_id not in CHANGES:
        raise ValueError('undeclared traffic sweep variant')
    if any(scene.get(key)!=value for key,value in BASE.items()
           if key.endswith('_start_x_m')):
        raise ValueError('traffic sweep baseline differs from authored scene')
    result=dict(scene)
    result.update(BASE)
    result.update(CHANGES[variant_id])
    if not (result['oncoming_start_x_m']>result['crossing_x_m']+10 and
            result['following_start_x_m']<result['start_x_m']-5 and
            -6<=result['oncoming_velocity_x_mps']<0 and
            0<result['following_velocity_x_mps']<=6):
        raise ValueError('traffic sweep geometry or velocity outside declared physical envelope')
    changed=tuple(CHANGES[variant_id])
    policy={'format':'c109755-traffic-sweep-v1','variant_id':variant_id,
            'basis':'authored 2 m/s baseline; one-factor physical challenges only',
            'legal_cutoff':None,'changed_knobs':list(changed),
            'oncoming_start_x_m':result['oncoming_start_x_m'],
            'following_start_x_m':result['following_start_x_m'],
            'oncoming_velocity_x_mps':result['oncoming_velocity_x_mps'],
            'following_velocity_x_mps':result['following_velocity_x_mps']}
    encoded=json.dumps(policy,sort_keys=True,separators=(',',':')).encode()
    return result,policy,hashlib.sha256(encoded).hexdigest()


def commanded_velocities(policy):
    if policy.get('format')!='c109755-traffic-sweep-v1' or policy.get('variant_id') not in CHANGES:
        raise ValueError('unknown traffic sweep policy')
    values={role:policy[role+'_velocity_x_mps'] for role in ('oncoming','following')}
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values.values()):
        raise ValueError('traffic sweep velocity invalid')
    return values
