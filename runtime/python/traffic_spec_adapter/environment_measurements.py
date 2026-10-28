"""Opt-in source-bound environmental measurements; historical omissions stay unknown."""
import hashlib,json,math
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def load(original):
    original=Path(original)
    p=original/'environment_calibration.json';s=original/'surface_provenance.json'
    if not p.exists() and not s.exists():return None
    if not p.exists() or not s.exists():raise ValueError('Incomplete environmental source packet')
    calibration=json.loads(p.read_text());surface=json.loads(s.read_text())
    if calibration.get('schema')!='rendered-target-contrast-range-v1' or not calibration.get('passed'):
        raise ValueError('Unverified environmental visibility calibration')
    if calibration.get('distance_kind') not in ('sampled_lower_bound','sampled_bracket'):
        raise ValueError('Visibility measurement must retain censoring')
    value=calibration.get('visibility_m')
    if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or value<=0:
        raise ValueError('Missing measured environmental distance')
    for record in calibration['samples']:
        for name in ('rgb','instance'):
            q=original/record[name]['path']
            if original not in q.resolve().parents or sha(q)!=record[name]['sha256']:
                raise ValueError('Environmental image source hash mismatch')
    if surface.get('schema')!='authored-native-road-surface-v1' or type(surface.get('ice_or_snow')) is not bool:
        raise ValueError('Missing explicit authored surface state')
    if surface.get('map_sha256')!=sha(original/'road.xodr') or not surface.get('source_assets') or not surface.get('authorship'):
        raise ValueError('Surface provenance not bound to realized native construction')
    # The fact is an explicit authored construction, not a precipitation inference.
    for asset in surface['source_assets']:
        if sha(asset['path'])!=asset['sha256']:raise ValueError('Surface source asset changed')
    return {'calibration':calibration,'surface':surface,'calibration_sha256':sha(p),'surface_sha256':sha(s)}

def project(packet,row,frame):
    if packet is None:return {},None
    m=row.get('environment_measurements')
    if not isinstance(m,dict) or m.get('frame')!=frame or abs(m.get('time_s',-1)-row['time_s'])>1e-6:
        raise ValueError('Missing same-frame environmental measurement join')
    for key in ('calibration_sha256','surface_sha256'):
        if m.get(key)!=packet[key]:raise ValueError('Environmental provenance join mismatch')
    c=packet['calibration'];s=packet['surface']
    if m.get('weather')!=c['weather']:raise ValueError('Atmosphere changed after rendered calibration')
    if m.get('visibility_m')!=c['visibility_m'] or m.get('ice_or_snow')!=s['ice_or_snow']:
        raise ValueError('Environmental measurement substituted')
    return {'visibility':c['visibility_m'],'ice_or_snow':s['ice_or_snow']},{'visibility_kind':c['distance_kind'],'visibility_method':c['method'],'visibility_uncertainty':c['uncertainty'],'surface_origin':'authored native construction; not inferred from precipitation','calibration_sha256':packet['calibration_sha256'],'surface_sha256':packet['surface_sha256']}
