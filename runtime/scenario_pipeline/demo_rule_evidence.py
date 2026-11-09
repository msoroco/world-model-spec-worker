"""Measured scenario expectations for the additional demo-law constructions.

Geometry is explicit scenario context, never inferred from a controller target.
Every ego footprint is checked against the original capture. Participant paths
and device states must be recorded at the same original ticks.
"""
import hashlib
import json
import math
from pathlib import Path


def contract():
    return __doc__ + '''
For deterministic probes of 113-2, 220-1, 227-1 and 250-1/2/4, write:
scenario_geometry.json: {source:<native-map or explicit authored geometry provenance>,
 physical_verification:<actual map/actor verification description>,
 intersection_polygon:[[x,y],...], stopping_approach_polygon:[[x,y],...],
 priority_actor_id:<observed actor ID>,
 prohibited_median_polygons:[polygon,...],
 directed_roadways:[{polygon:polygon,direction_xy:[dx,dy]}],
 direction_sign_actor_ids:[actual actor or native environment-object IDs],
 direction_sign_objects:[{id,native_name,position_m,governs_roadway_indices:[zero-based directed_roadways index]}], inoperative_signal_actor_ids:[IDs]}.
Only fields needed by the target law are required. Use CARLA world XY metres.
Write scenario_rule_evidence.jsonl per captured tick:
{frame,time_s,value:{ego_body_xy:[[x,y],...],
 participants:[{actor_id,body_xy:[[x,y],...],position_m:[x,y,z],speed_mps}],
 devices:[{actor_id,state}]}}.
The stopping_approach_polygon is the verified stopping position immediately before
the applicable line/crosswalk, not the entire approach or initial spawn area.
Bodies come from actual bounding-box world vertices (convex hull in XY), never
requested poses. Devices come from actual actor or native environment-object queries. Native one-way signs must include native_name and position_m in every devices observation. Set directed_roadways[].one_way true for a one-way region. The native one-way sign SM_oneWayR_2502_SM_0 in Town10HD_Opt is genuine and rendered; generic streetsign props are advertisement boards. Participant position_m must be measured bounding-box body centre (not actor origin), matching the delivered Core track. Capture all participants
and joined native graph evidence. Preserve the scene's declared geometry and
authority context in scene_assumptions and the final adapter context.
For 250-2, approximately-simultaneous timing remains unresolved unless an explicit
fixed simultaneous-approach assumption is declared; never invent a time cutoff.
For 250-4 deterministic stop/yield probes, fix other subjective conditions
explicitly; actual cautiousness sweeps remain unlabeled. Set expected_label_specification
with intended_outcome and scene_assumptions in the case or scene_assumptions in
config.json. The evaluator does not read a requested label as measured evidence.
'''


def evaluate(case, attempt, trace, context):
    from shapely.geometry import Polygon, MultiPoint
    def polygon(vertices):
        p = Polygon(vertices)
        if not p.is_valid or p.area <= 0:
            raise ValueError('Invalid recorded reference polygon')
        return p
    def read_rows(path):
        return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    attempt = Path(attempt)
    geometry_path = attempt/'scenario_geometry.json'
    geometry = json.loads(geometry_path.read_text())
    if not geometry.get('source') or not geometry.get('physical_verification'):
        raise ValueError('Physical reference provenance and verification required')
    samples = read_rows(attempt/'scenario_rule_evidence.jsonl')
    original = read_rows(attempt/'capture/evidence.jsonl')
    if not trace or len(samples) != len(trace) or len(original) != len(trace):
        raise ValueError('Complete original-tick rule evidence required')
    scenes=json.loads((attempt/'traffic_spec/trace.json').read_text())['scenes']
    if len(scenes)!=len(trace):raise ValueError('Full delivered scene join required')
    bodies=[]
    for t,s,o,scene in zip(trace,samples,original,scenes):
        if s['frame'] != t['frame'] or abs(s['time_s']-t['time_s']) > 1e-6 or o['original_frame'] != t['frame']:
            raise ValueError('Rule evidence does not join original trace ticks')
        measured=MultiPoint(s['value']['ego_body_xy']).convex_hull
        captured=MultiPoint([v[:2] for v in o['ego']['body_vertices_m']]).convex_hull
        if measured.area <= 0 or measured.hausdorff_distance(captured)>1e-4:
            raise ValueError('Rule ego footprint differs from original capture')
        bytrack={u['track']:u for u in scene['users']}
        for participant in s['value'].get('participants',[]):
            delivered=bytrack.get(participant['actor_id'])
            if delivered is None:raise ValueError('Required participant missing from delivered scene')
            pos=participant['position_m'];kin=delivered['kin']
            if math.hypot(pos[0]-kin['position'][0],-pos[1]-kin['position'][1])>1e-4 or abs(participant['speed_mps']-kin['speed'])>1e-4:
                raise ValueError('Participant observations differ from delivered scene')
        bodies.append(measured)
    law=case['target_law_id']
    intended=case.get('expected_label_specification',{}).get('intended_outcome')
    if intended is None:
        intended='non_compliant' if case.get('target_type')=='violating_attempt' else 'compliant'
    evidence={'geometry_reference':str(geometry_path),
              'geometry_sha256':hashlib.sha256(geometry_path.read_bytes()).hexdigest(),
              'source':geometry['source'],'physical_verification':geometry['physical_verification'],
              'samples':len(samples),'scope':'Every original captured tick'}
    violating=[]
    if law=='NRS-484B-113-2':
        intersection=polygon(geometry['intersection_polygon'])
        for t,b in zip(trace,bodies):
            v=t['velocity_mps'];yaw=math.radians(t['heading_deg'])
            reversing=v[0]*math.cos(yaw)+v[1]*math.sin(yaw)<-1e-6
            if reversing and b.intersection(intersection).area>1e-8:violating.append(t['frame'])
        evidence['measurement']='Observed reverse longitudinal velocity and body overlap of the declared intersection boundary'
    elif law in ('NRS-484B-220-1','NRS-484B-227-1'):
        roadways=[(polygon(r['polygon']),r['direction_xy']) for r in geometry['directed_roadways']]
        medians=[polygon(p) for p in geometry.get('prohibited_median_polygons',[])]
        if law=='NRS-484B-220-1':
            signs=set(geometry['direction_sign_actor_ids'])
            if not signs or not all(signs <= {d['actor_id'] for d in s['value']['devices']} for s in samples):
                raise ValueError('Recorded actual direction-sign actors required')
        elif not medians:
            raise ValueError('Recorded prohibited median/dividing-space geometry required')
        for t,b in zip(trace,bodies):
            v=t['velocity_mps']
            wrong=any(b.intersection(p).area>1e-8 and v[0]*d[0]+v[1]*d[1]<-1e-6 for p,d in roadways)
            crossed=any(b.intersection(p).area>1e-8 for p in medians)
            if wrong or crossed:violating.append(t['frame'])
        evidence['measurement']='Measured body overlap of prohibited dividing regions and velocity against recorded roadway direction; openings excluded explicitly from prohibited regions'
    else:
        intersection=polygon(geometry['intersection_polygon'])
        ego_inside=[b.intersection(intersection).area>1e-8 for b in bodies]
        entries=[i for i in range(1,len(trace)) if ego_inside[i] and not ego_inside[i-1]]
        if not entries:raise ValueError('Observed intersection entry required')
        other_inside={}
        for i,s in enumerate(samples):
            for u in s['value']['participants']:
                other_inside.setdefault(u['actor_id'],[False]*len(samples))[i]=polygon(u['body_xy']).intersection(intersection).area>1e-8
        if law in ('NRS-484B-250-1','NRS-484B-250-2'):
            if not other_inside:raise ValueError('Recorded cross-highway participant required')
            priority=context.get('priority_actor_id',geometry.get('priority_actor_id'))
            if priority not in other_inside:raise ValueError('Explicit priority participant identity required')
            if law.endswith('250-2') and not context.get('fixed_simultaneous_approach'):
                raise ValueError('Approximate simultaneity unresolved; use a judgment sweep or explicit fixed context')
            prior=other_inside[priority]
            if law.endswith('250-1') and not any(prior[:entries[0]]):
                raise ValueError('Other vehicle not observed entering before ego')
            violating=[trace[i]['frame'] for i in entries if prior[i]]
            evidence['measurement']='Recorded priority actor occupancy at ego entry under the declared single-conflict crossing context'
            evidence['priority_actor_id']=priority
        else:
            signals=set(geometry['inoperative_signal_actor_ids'])
            if not signals or not all(signals <= {d['actor_id'] for d in s['value']['devices'] if str(d['state']).lower() in ('off','inoperative')} for s in samples):
                raise ValueError('Installed inoperative signal states required at every tick')
            stop_zone=polygon(geometry['stopping_approach_polygon'])
            before=[i for i,b in enumerate(bodies) if stop_zone.covers(b) and i<entries[0]]
            stopped=any(trace[i]['speed_mps']<=1e-5 for i in before)
            if not context.get('fixed_non_swept_conditions'):
                raise ValueError('Other subjective conditions must be fixed for deterministic stop/yield probe')
            violating=[trace[i]['frame'] for i in entries if not stopped or any(v[i] for v in other_inside.values())]
            evidence.update(measurement='Observed stop before declared reference and participant occupancy at entry',stop_observed=stopped)
    evidence['violation_frames']=violating
    return {'expected_label':'non_compliant' if violating else 'compliant',
            'intended_outcome':intended,'evidence':evidence}
