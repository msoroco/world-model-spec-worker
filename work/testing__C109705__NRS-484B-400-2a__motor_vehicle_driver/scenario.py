"""Law-specific physical branch selection and observed geometry; no legal verdict."""
import math

def route(c,case):
    v=case['variable_assignments']; law=c['law_id']
    lateral=v.get('commanded_approach_lateral_m',{}).get('value',1.75)
    destination=v.get('commanded_exit_lateral_m',{}).get('value',1.75)
    if law.endswith(('400-2a','400-2b','253')):
        start=-7; end=-7
        p=[[-80+i,lateral] for i in range(74)]
        # Cubic Bezier preserves approach/exit tangents; whole route remains fixed across speed sweeps.
        a=(-7,lateral);b=(destination-5,lateral);d=(destination,-7);cc=(destination,-2)
        for i in range(1,41):
            t=i/40;u=1-t;p.append([u**3*a[j]+3*u*u*t*b[j]+3*u*t*t*cc[j]+t**3*d[j] for j in range(2)])
        p += [[destination,-7-i] for i in range(1,54)]
        return p
    if law.endswith('223-1b'):
        return [[-80+i,1.75+3.5*(.5-.5*math.cos(math.pi*max(0,min(1,(i-40)/30))))] for i in range(141)]
    return c['path']

def footprint_gap(ego,other):
    a=ego.bounding_box.get_world_vertices(ego.get_transform());b=other.bounding_box.get_world_vertices(other.get_transform())
    # Straight eastbound following only; retain raw vertices for arbitrary-path downstream geometry.
    return min(p.x for p in b)-max(p.x for p in a)

def physical_sample(ego,path,others,world):
    t=ego.get_transform();p=t.location;velocity=ego.get_velocity()
    near=min(math.hypot(p.x-x,p.y-y) for x,y in path)
    return dict(position_m=[p.x,p.y,p.z],heading_deg=t.rotation.yaw,speed_mps=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),route_error_m=near,
        body_vertices_m=[[v.x,v.y,v.z] for v in ego.bounding_box.get_world_vertices(t)],
        participants=[dict(actor_id=a.id,position_m=[a.get_location().x,a.get_location().y,a.get_location().z],body_vertices_m=[[v.x,v.y,v.z] for v in a.bounding_box.get_world_vertices(a.get_transform())]) for a in others],
        gap_m=footprint_gap(ego,others[0]) if others else None,ego_lamp_bits=int(ego.get_light_state()),
        devices=[dict(actor_id=a.id,state=str(a.get_state())) for a in world.get_actors().filter('traffic.traffic_light*')])

def target_checks(case,samples):
    v=case['variable_assignments'];out=[]
    if not samples:return out
    for key,window,coordinate in [('commanded_approach_lateral_m',lambda s:s['position_m'][0]<-10,1),('commanded_exit_lateral_m',lambda s:s['position_m'][1]<-12,0)]:
        if key in v:
            values=[s['position_m'][coordinate] for s in samples if window(s)]
            measured=sum(values)/len(values) if values else None
            out.append(dict(target=key,requested=v[key]['value'],measured=measured,method='mean actual CARLA position in stated approach/exit window',tolerance=.35,matched=measured is not None and abs(measured-v[key]['value'])<=.35,physical_cause_confirmed=None,cause_evidence='physical_samples.jsonl; native roadway verification still required'))
    if 'commanded_gap_m' in v:
        vals=[s['gap_m'] for s in samples if s['gap_m'] is not None];value=sum(vals[-100:])/len(vals[-100:]) if vals else None
        out.append(dict(target='commanded_gap_m',requested=v['commanded_gap_m']['value'],measured=value,method='mean final up-to-100 straight-road footprint gaps',tolerance=2,matched=value is not None and abs(value-v['commanded_gap_m']['value'])<=2,physical_cause_confirmed=bool(vals),cause_evidence='physical_samples.jsonl actual body vertices'))
    if 'commanded_halt' in v:
        values=[s['speed_mps'] for s in samples if -20<s['position_m'][0]<-8];value=min(values) if values else None
        out.append(dict(target='commanded_halt',requested=v['commanded_halt']['value'],measured=value,method='minimum observed speed before intersection; full raw history retained, no legal duration invented',tolerance=None,matched=None,physical_cause_confirmed=None,cause_evidence='physical_samples.jsonl and native sign/crosswalk hierarchy audit pending'))
    return out
