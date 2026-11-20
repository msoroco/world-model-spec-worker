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


def _straight_source_approaches(path):
    """Complete native map candidates; a requested route is not evidence."""
    import xml.etree.ElementTree as ET
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from traffic_spec_adapter.geometry import static_map
    root=ET.parse(path).getroot()
    if root.tag!='OpenDRIVE':return {},set()
    sources={}
    regions,_,_=static_map(path,partial=False,complete_map=True,source_regions=sources)
    candidates={};straight=set()
    for road in root.findall('road'):
        rid=int(road.get('id'));geometry=road.findall('./planView/geometry')
        lanes=[r for r in regions if r['kind']=='lane' and sources.get(r['id'],{}).get('road_id')==rid]
        if not lanes:continue
        shape=unary_union([Polygon(r['boundary'])for r in lanes])
        if shape.is_valid and not shape.is_empty:candidates[rid]=shape
        sections=road.findall('./lanes/laneSection');offsets=road.findall('./lanes/laneOffset')
        def constant(record,start):
            return (all(k in record.attrib for k in (start,'a','b','c','d'))and
                    all(math.isfinite(float(record.get(k)))for k in (start,'a','b','c','d'))and
                    float(record.get(start))==0 and
                    all(float(record.get(k))==0 for k in ('b','c','d')))
        if (road.get('junction','-1')!='-1' or len(geometry)!=1 or geometry[0].find('line')is None
                or len(sections)!=1 or float(sections[0].get('s'))!=0
                or len(offsets)>1 or any(not constant(o,'s')for o in offsets)):continue
        lateral=sections[0].findall('./left/lane')+sections[0].findall('./right/lane')
        if any(len(l.findall('width'))!=1 or not constant(l.find('width'),'sOffset')or
               float(l.find('width').get('a'))<=0 for l in lateral):continue
        straight.add(rid)
    return candidates,straight


def reviewed_backing(case, attempt, trace, scope_path):
    """Join a reviewed native boundary to original bodies and current Core data.

    A prior verdict is never an input. The scope binds immutable source files;
    current subject identity, time, motion and boundary are checked every frame.
    """
    from itertools import zip_longest
    from shapely.geometry import Polygon
    from traffic_spec_adapter.geometry import body,normalized_polygon
    from trace_json import scenes
    attempt=Path(attempt);scope_path=Path(scope_path)
    if not trace:raise ValueError('Native backing source trace is empty')
    scope=json.loads(scope_path.read_text())
    if scope.get('schema')!='reviewed-backing-observation-scope-v1' or scope.get('case_id')!=case.get('case_id') or scope.get('law_id')!=case.get('target_law_id'):
        raise ValueError('Native backing scope identity differs from frozen case')
    roots=list(dict.fromkeys((attempt,scope_path.parent)))
    used={str(scope_path):hashlib.sha256(scope_path.read_bytes()).hexdigest()}
    def source(name,expected):
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts or not expected:
            raise ValueError('Invalid native backing source reference')
        matches=[]
        for root in roots:
            path=root/relative
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==expected:matches.append(path)
        if not matches:raise ValueError('Native backing source missing or changed: '+name)
        path=matches[0];used[str(path)]=expected
        return path
    paths={name:source(name,checksum)for name,checksum in scope.get('sources',{}).items()}
    required={'trace.jsonl','road.xodr','capture/manifest.json','capture/native_map_facts.json',
              'intersection_boundary_review.json','scenario_geometry.json','report_recovery.json'}
    if not required<=set(paths):raise ValueError('Native backing scope lacks mandatory source bindings')
    if json.loads(paths['trace.jsonl'].read_text().splitlines()[0]).get('frame')!=trace[0].get('frame'):
        raise ValueError('Native backing source starts at a different frame')
    manifest=json.loads(paths['capture/manifest.json'].read_text())
    if manifest.get('acquisition')!='original_live_run':raise ValueError('Native backing requires original acquisition')
    recovery=json.loads(paths['report_recovery.json'].read_text())
    capture_path=source('capture/evidence.jsonl',recovery.get('source_files',{}).get('capture/evidence.jsonl'))
    boundary=json.loads(paths['intersection_boundary_review.json'].read_text())
    if boundary.get('map_sha256')!=scope['sources']['road.xodr'] or boundary.get('rendered_review_confirmed') is not True:
        raise ValueError('Native backing boundary is not map/render bound')
    for name,checksum in boundary.get('sources',{}).items():source(name,checksum)
    geometry=json.loads(paths['scenario_geometry.json'].read_text())
    verification=geometry.get('physical_verification',{})
    if not isinstance(verification,dict) or verification.get('review')!='intersection_boundary_review.json' or verification.get('sha256')!=scope['sources']['intersection_boundary_review.json']:
        raise ValueError('Native backing geometry verification differs')
    reference=Polygon(normalized_polygon(boundary['boundary_core_m']))
    rid=scope.get('intersection_region_core_id')
    if type(rid)is not int:raise ValueError('Native backing intersection identity missing')
    violating=[];count=0;first_heading=None;first_centre=None;first_actor=None;previous=None;straight=True
    approaches,straight_roads=_straight_source_approaches(paths['road.xodr'])
    approach_id=None;contained_approach=True
    def rows(path):
        with path.open() as stream:
            for line in stream:
                if line.strip():yield json.loads(line)
    current=attempt/'traffic_spec/trace.json'
    used[str(current)]=hashlib.sha256(current.read_bytes()).hexdigest()
    # The supplied trace must itself be exactly the source-bound raw stream.
    if list(rows(paths['trace.jsonl']))!=trace:raise ValueError('Native backing raw trace differs from scope')
    for raw,packet,scene_row in zip_longest(trace,rows(capture_path),scenes(current)):
        if raw is None or packet is None or scene_row is None:raise ValueError('Incomplete native backing frame membership')
        scene=scene_row[0];count+=1
        if any(not isinstance(value,(int,float))or isinstance(value,bool)or not math.isfinite(value) for value in (raw['time_s'],raw['heading_deg'],packet['recording_time_s'],packet['ego']['heading_deg'],*raw['velocity_mps'])):
            raise ValueError('Nonfinite or invalid original backing telemetry')
        if previous is not None and (raw['frame']<=previous[0] or raw['time_s']<=previous[1]):
            raise ValueError('Native backing original frames/times do not increase')
        previous=(raw['frame'],raw['time_s'])
        if packet.get('original_frame')!=raw['frame'] or packet.get('replay_frame')!=raw['frame'] or abs(packet['recording_time_s']-raw['time_s'])>1e-6 or scene['t']!=round(raw['time_s']*1000):
            raise ValueError('Native backing original/Core time join differs')
        aid=packet['actor_id']
        if first_actor is None:first_actor=aid
        if aid!=first_actor:raise ValueError('Native backing original subject changes')
        if scene.get('subject')!=aid:raise ValueError('Native backing subject identity differs')
        users=[u for u in scene.get('users',[])if u.get('track')==aid]
        if len(users)!=1:raise ValueError('Native backing subject missing or duplicated')
        kin=users[0].get('kin',{})
        centre,extent,footprint=body(packet['ego']['body_vertices_m'],packet['ego']['heading_deg'])
        expected_heading=[math.cos(math.radians(raw['heading_deg'])),-math.sin(math.radians(raw['heading_deg']))]
        native_heading=[math.cos(math.radians(packet['ego']['heading_deg'])),-math.sin(math.radians(packet['ego']['heading_deg']))]
        if max(abs(a-b)for a,b in zip(native_heading,expected_heading))>1e-6:
            raise ValueError('Native backing source headings disagree')
        velocity=raw['velocity_mps'];expected_velocity=[velocity[0],-velocity[1]]
        for field,expected,tolerance in [('position',centre[:2],1e-4),('extent',extent[:2],1e-4),('heading',expected_heading,1e-6),('velocity',expected_velocity,1e-6)]:
            values=kin.get(field)
            if not isinstance(values,list) or len(values)<2 or any(not isinstance(v,(int,float))or isinstance(v,bool)or not math.isfinite(v) for v in values[:2]) or any(abs(a-b)>tolerance for a,b in zip(values[:2],expected)):
                raise ValueError('Native backing current subject '+field+' differs from original')
        regions=[r for r in scene.get('structures',[])if r.get('id')==rid]
        if len(regions)!=1 or regions[0].get('kind')!='intersection':raise ValueError('Native backing target intersection missing or changed')
        delivered=Polygon(normalized_polygon(regions[0]['boundary']))
        if delivered.hausdorff_distance(reference)>1e-6:raise ValueError('Native backing current boundary differs from reviewed native source')
        if first_heading is None:first_heading=expected_heading;first_centre=centre
        # Measurement consistency bounds, not a legal threshold for a corner.
        if max(abs(a-b)for a,b in zip(first_heading,expected_heading))>1e-6 or abs((centre[0]-first_centre[0])*first_heading[1]-(centre[1]-first_centre[1])*first_heading[0])>1e-4:straight=False
        # All actual bodies must remain on ONE uniquely identified, nonjunction
        # straight native approach. Small real steering corrections are kept;
        # neither numeric straightness nor requested controller intent is assumed.
        matches=[road for road,shape in approaches.items()if shape.intersection(footprint).area>0]
        if (len(matches)!=1 or matches[0]not in straight_roads or not approaches[matches[0]].covers(footprint)
                or (approach_id is not None and matches[0]!=approach_id)):contained_approach=False
        elif approach_id is None:approach_id=matches[0]
        projection=sum(a*b for a,b in zip(expected_velocity,expected_heading))
        if projection < -1e-6 and footprint.intersection(reference).area>1e-8:violating.append(raw['frame'])
    absence_complete=False
    absence_path=paths.get('scene_absence_review.json')
    if absence_path:
        absence=json.loads(absence_path.read_text());entry=absence.get('atoms',{}).get('st.crosswalk',{})
        absence_complete=(entry.get('status')=='verified_absent' and entry.get('scope')=='entire_recorded_scene' and entry.get('unresolved')==[] and absence.get('frames')==[r['frame']for r in trace])
        if absence_complete:
            if not entry.get('evidence'):raise ValueError('Native backing absence lacks source proof')
            for ref in entry['evidence']:source(ref['path'],ref['sha256'])
    for name,checksum in used.items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=checksum:raise ValueError('Native backing evidence changed during evaluation')
    no_corner=contained_approach and approach_id is not None
    outcome='violation' if violating else 'compliant' if absence_complete and no_corner else None
    return {'expected_label':outcome,
        'processing_reasons':[] if outcome else ['unsupported_evaluation'],
        'evidence':{'measurement':'Original horizontal reverse projection and full body overlap of source-verified native intersection; current Core joins checked every frame',
            'geometry_reference':str(paths['intersection_boundary_review.json']),
            'samples':count,'violation_frames':violating,'straight_within_observation_resolution':straight,
            'single_straight_native_approach':approach_id if no_corner else None,
            'crosswalk_absence_source_complete':absence_complete,'source_hashes':used,
            'scope':'Full recording under the retained native boundary and crosswalk-absence interpretation'}}


def evaluate(case, attempt, trace, context):
    if case.get('target_law_id')=='NRS-484B-113-2':
        for scope in (Path(attempt)/'backing_observation_scope.json',Path(attempt)/'delivery/scene_evidence/backing_observation_scope.json'):
            if scope.is_file():return reviewed_backing(case,attempt,trace,scope)
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
