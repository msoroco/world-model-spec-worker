"""Convert a raw recorded capture into TrafficSpec's runtime data, without laws.

Native replay kinematics are not original telemetry. Incoming virtual-observer
rays are not rel.visible. Declared any-body horizons supply regional sight distance. Supplementary output retains every
source evidence record, original telemetry record and a hashed raw-graph reference.
Pickles must be trusted local captures; the loader is not a security sandbox.
"""
import hashlib
import json
import math
import pickle
import re
from pathlib import Path
from .geometry import body, static_map, xy, painted_map_objects, native_centre_lines
from .visibility import attach_visibility

VERSION = 'traffic-spec-original-observation-adapter-v6-physical-animal-registry'


class CarlaValue:
    def __new__(cls, *args):
        obj = object.__new__(cls); obj.args = args; return obj


class GraphLoader(pickle.Unpickler):
    def persistent_load(self, identifier):
        if identifier != 'please_ignore_me':
            raise ValueError('Unknown persistent graph reference')
        return None

    def find_class(self, module, name):
        if module == 'carla.libcarla':
            return CarlaValue
        return super().find_class(module, name)


def load_graph(path):
    with Path(path).open('rb') as stream:
        return GraphLoader(stream).load()


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def rounded(value):
    if isinstance(value, bool) or value is None or isinstance(value,(str,int)):return value
    if isinstance(value,float):
        if not math.isfinite(value):raise ValueError('Nonfinite measurement')
        return round(value,6)
    if isinstance(value,dict):return {k:rounded(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [rounded(v) for v in value]
    raise ValueError('Unsupported JSON value '+str(type(value)))


def serialized_scene(scene, original_precision=False):
    value=rounded(scene)
    if original_precision:
        # Quantization must not turn a tiny measured threshold exceedance into
        # equality. Validate all types/finiteness first; retain numeric telemetry.
        for user,source in zip(value['users'],scene['users']):
            user['kin']=dict(source.get('kin',{}))
    return value


def rows(path):
    with Path(path).open() as f:return [json.loads(line) for line in f if line.strip()]


def full_core(library):
    library=Path(library)
    active=library/'splits/ACTIVE'
    if active.exists() and active.read_text().strip()!='full':
        core=library/'splits/full/TrafficSpec/Core'
    else:core=library/'TrafficSpec/Core'
    if not (core/'Runtime/Decode.lean').exists():raise ValueError('Full TrafficSpec Core unavailable')
    return core


def atom_ids(library):
    text=(full_core(library)/'Vocab/Ontology/Ids.lean').read_text()
    block=re.search(r'def atomIds : List String := \[(.*?)\]',text,re.S)
    if block is None:raise ValueError('Full ontology atomIds declaration missing')
    return re.findall(r'"([a-z]+\.[a-z_]+)"',block.group(1))


def manifest(library, original_live=False, visibility_observed=False, *, extended_observations=False, road_user_visibility=False, wheel_angles=False):
    """Capability of this recorded-capture adapter, not presence in one scene.

    All other atoms stay absent. Per-frame omissions remain unknown even for a
    supported capability. Curved lanes lack a single global direction; dynamic
    crosswalks and complete device inventories were not captured by this
    acquisition path. Do not copy the optimistic example manifest.
    """
    observed={'ru.subject':'exact','ru.aggregate':'exact','ru.motor_vehicle':'exact',
              'ru.pedestrian':'exact','ru.bicycle':'estimate:blueprint_classification',
              'ru.motorcycle':'estimate:blueprint_classification',
              'kin.time':'exact','kin.position':'exact','kin.heading':'exact','kin.extent':'exact',
              'kin.speed':'exact' if original_live else 'subject',
              'kin.velocity':'exact' if original_live else 'subject',
              'kin.yaw_rate':'subject','kin.path_length':'subject',
              'kin.throttle':'subject','kin.service_brake':'subject','kin.parking_brake':'subject',
              'st.lane':'exact','st.roadway':'exact','st.lane_direction':'exact',
              'st.lane_adjacency':'exact','st.lane_width':'exact',
              'st.lane_marking':'exact','st.curvature':'exact','st.grade':'exact',
              'st.intersection':'estimate:native_junction_geometry',
              'st.centre_line':'estimate:native_opposing_lane_divider',
              'st.lane_enters':'exact',
              'st.stop_line':'estimate:native_painted_map_object',
              'st.crosswalk':'estimate:native_map_object',
              'st.region_geometry':'estimate:sampled_map_and_recorded_body_geometry',
              'st.obstruction':'estimate:recorded_traffic_prop',
              'st.sight_distance':('estimate:subject_relative_any_body_sampled_minimum' if visibility_observed else 'absent'),
              'rel.occupies':'estimate:sampled_polygon_overlap',
              'env.darkness':'estimate:sun_below_horizon',
              'env.precipitation':'estimate:positive_precipitation_parameter',
              'env.wet_road':'estimate:positive_wetness_parameter',
              'rel.centre_distance':'exact','rel.surface_gap':'exact',
              'rel.ahead_behind_in_lane':'exact','rel.longitudinal_overlap':'exact',
              'rel.oncoming':'exact','rel.same_direction':'exact','rel.bearing':'exact','rel.contact':'estimate:planar_recorded_body_overlap_not_a_collision_sensor',
              'dev.traffic_signal':'exact','dev.stop_sign':'exact',
              'dev.yield_sign':'estimate:landmark_type','dev.speed_limit_sign':'exact',
              'dev.position':'exact','dev.governs':'exact',
              'sig.brake_lamp':'exact','sig.position_lamp':'exact',
              'sig.reverse_lamp':'exact','sig.hazard':'exact','sig.headlamp':'exact','sig.turn_indicator':'exact'}
    if extended_observations:
        observed['kin.accel_longitudinal'] = 'exact'
        observed['ru.bus'] = 'estimate:recorded_native_blueprint_base_type'
        observed['ru.truck'] = 'estimate:recorded_native_blueprint_base_type'
        observed['ru.child'] = 'estimate:recorded_native_walker_age_class'
        observed['st.sidewalk'] = 'estimate:native_lane_surface_role'
        observed['st.shoulder'] = 'estimate:native_lane_surface_role'
        observed['st.lane_connectivity'] = 'estimate:explicit_native_lane_links'
    if wheel_angles:
        observed['kin.steer_angle'] = 'subject'
    if road_user_visibility:
        observed['rel.visible'] = 'subject'
    ids=atom_ids(library)
    if not ids:raise ValueError('No ontology atom IDs found')
    return {'source':VERSION,'reid_gap':0,'atoms':{k:observed.get(k,'absent') for k in ids}}


def rates(times, headings):
    """Unwrap reflected actual heading; difference adjacent samples, deg/s.

    Interior samples use the central difference, endpoints one-sided. A gap
    exceeding 1.5 times the median period or a >90-degree jump leaves that rate
    unknown instead of interpolating across lost evidence.
    """
    if len(times)<2:return [None]*len(times)
    deltas=[times[i]-times[i-1] for i in range(1,len(times))]
    period=sorted(deltas)[len(deltas)//2]; angles=[-headings[0]]
    jumps=[]
    for i in range(1,len(times)):
        delta=(-headings[i]+headings[i-1]+180)%360-180
        angles.append(angles[-1]+delta);jumps.append(abs(delta)>90 or deltas[i-1]>1.5*period)
    result=[]
    for i in range(len(times)):
        a=max(0,i-1);b=min(len(times)-1,i+1)
        result.append(None if any(jumps[a:b]) else (angles[b]-angles[a])/(times[b]-times[a]))
    return result


def live_kinematics(attrs, acquisition):
    """Only original-frame actor telemetry can establish participant motion.

    Recorder replay graph velocities can be zero artifacts and remain unknown.
    """
    if acquisition != 'original_live_run':
        return {}
    result={}
    if 'carla_speed' in attrs:
        result['speed']=attrs['carla_speed']
    if all('carla_acc_'+axis in attrs for axis in ('x','y','z')) and 'forward' in attrs:
        result['accel_longitudinal']=sum(attrs['carla_acc_'+axis]*v for axis,v in zip(('x','y','z'),attrs['forward']))
    if all('carla_vel_'+axis in attrs for axis in ('x','y')):
        result['velocity']=[attrs['carla_vel_x'],-attrs['carla_vel_y']]
    return result


def original_participants(path, evidence, acquisition):
    """Join original actor telemetry; replay and command values never establish motion."""
    if not path.exists():return {}
    if acquisition != 'original_live_run':raise ValueError('Participant telemetry requires original live acquisition')
    records=rows(path); result={}
    expected={e['original_frame']:e for e in evidence}
    for row in records:
        value=row['value'];frame=value['frame']
        if frame in result or frame not in expected:raise ValueError('Invalid participant frame join')
        if abs(row['time_s']-expected[frame]['recording_time_s'])>1e-6:raise ValueError('Participant timestamp mismatch')
        actors={}
        for actor in value.values():
            if not isinstance(actor,dict) or 'actor_id' not in actor:continue
            aid=actor['actor_id']
            if aid in actors:raise ValueError('Duplicate participant identity')
            rounded(actor)
            velocity=actor['velocity_mps']
            if len(velocity)!=3 or abs(math.sqrt(sum(v*v for v in velocity))-actor['speed_mps'])>1e-5:
                raise ValueError('Participant speed/velocity mismatch')
            body(actor['body_vertices_m'],actor['heading_deg'])
            if not actor['blueprint'].startswith(('vehicle.','walker.')):raise ValueError('Unsupported participant class')
            actors[aid]=actor
        if expected[frame]['actor_id'] not in actors:raise ValueError('Participant stream missing subject')
        subject=actors[expected[frame]['actor_id']]
        if abs(subject['speed_mps']-expected[frame]['ego']['speed_mps'])>1e-5:raise ValueError('Participant subject speed mismatch')
        result[frame]=actors
    if set(result)!=set(expected):raise ValueError('Incomplete participant frame coverage')
    return result


def attach_original_participants(users, footprints, actors, subject, library):
    """Retain measured tracks outside the graph crop without inventing visibility."""
    by_id={u['track']:u for u in users}
    for aid,actor in actors.items():
        if aid==subject:continue
        centre,extent,footprint=body(actor['body_vertices_m'],actor['heading_deg'])
        h=math.radians(-actor['heading_deg'])
        kin={'position':centre,'heading':[math.cos(h),math.sin(h)],'extent':extent,
             'speed':actor['speed_mps'],'velocity':xy(actor['velocity_mps'])}
        if aid in by_id:
            previous=by_id[aid]['kin']
            for key in ('position','heading','extent'):
                if key in previous and any(abs(a-b)>1e-4 for a,b in zip(previous[key],kin[key])):
                    raise ValueError('Participant graph/telemetry geometry mismatch: '+key)
            if 'speed' in previous and abs(previous['speed']-kin['speed'])>1e-5:
                raise ValueError('Participant graph/telemetry speed mismatch')
            user=by_id[aid]
        else:
            found,unknown=classes(actor['blueprint'],library,actor.get('blueprint_attributes'),actor.get('physical_classification'))
            user={'track':aid,'classes':found,'unobserved_classes':unknown,'kin':{}}
            users.append(user);by_id[aid]=user
        user['kin'].update(kin);footprints[aid]=footprint


def classes(sem, library, attributes=None, physical_classification=None):
    if sem.startswith('vehicle.'):
        found=['motor_vehicle']
        if 'motorcycle' in sem:found.append('motorcycle')
        if 'bicycle' in sem or any(n in sem for n in ('crossbike','omafiets','century')):found=['bicycle']
    elif sem.startswith('walker.'):found=['pedestrian']
    elif physical_classification and sem=='static.prop.mesh' and physical_classification.get('physical_class')=='animal':found=['animal']
    else:return None,[]
    base=(attributes or {}).get('base_type')
    known={'motor_vehicle','pedestrian','bicycle','motorcycle','animal'}
    if sem.startswith('walker.'):
        known.update(('bus','truck','child'))
        if (attributes or {}).get('age') not in ('adult','child'):known.discard('child')
        elif attributes['age']=='child':found.append('child')
    if base in ('car','bus','truck','motorcycle','bicycle'):known.update(('bus','truck'))
    if base in ('bus','truck','motorcycle') and sem.startswith('vehicle.'):
        if base not in found:found.append(base)
    text=(full_core(library)/'Vocab/Ontology/RoadUser.lean').read_text()
    start=text.index('namespace RoadUserClass')
    enum=re.findall(r'\| "([a-z_]+)" => some',text[start:text.index('def toString',start)])
    # Unestablished subclasses are unknown, not automatically false.
    return found,[c for c in enum if c not in found and c not in known]


def signals(attrs):
    """Map recorded lamps only; never infer them from throttle/brake/steering."""
    result={}
    for source,target in [('light_Brake','brake_lamp'),('light_Position','position_lamp'),('light_Reverse','reverse_lamp')]:
        if source in attrs:result[target]=bool(attrs[source])
    if 'light_LeftBlinker' in attrs and 'light_RightBlinker' in attrs:
        left,right=bool(attrs['light_LeftBlinker']),bool(attrs['light_RightBlinker'])
        result['hazard']=left and right
        if left!=right:result['turn_indicator']='left' if left else 'right'
        # Core has no 'off' or 'hazard' TurnSide: keep indicator unknown there.
    if 'light_HighBeam' in attrs and 'light_LowBeam' in attrs:
        result['headlamp']='high_beam' if attrs['light_HighBeam'] else ('low_beam' if attrs['light_LowBeam'] else 'off')
    return result


def device_record(node, attrs, graph, lane_ids):
    sem=attrs.get('sem_class',''); kind=None
    if sem=='traffic.traffic_light':kind='traffic_signal'
    elif sem=='traffic.stop':kind='stop_sign'
    elif sem.startswith('traffic.speed_limit.'):kind='speed_limit_sign'
    elif 'landmark_type' in attrs:
        kind={'206':'stop_sign','205':'yield_sign','274':'speed_limit_sign'}.get(str(attrs['landmark_type']))
    if kind is None:return None,None
    actor=attrs.get('carla_id',attrs.get('entity_id')); landmark=attrs.get('landmark_id')
    if actor is None and landmark is None:raise ValueError('Device lacks stable identity')
    key=('landmark',str(landmark)) if landmark is not None else ('actor',str(actor))
    record={'kind':kind}
    if 'vertex' in attrs:record['position']=xy(attrs['vertex'])
    governs=set()
    for _,target,edge in graph.out_edges(node,data=True):
        if edge.get('dist_relationship',edge.get('label'))!='controlsTrafficOf':continue
        a=graph.nodes[target]
        k=(a.get('waypoint_road_id'),a.get('waypoint_section_id'),a.get('waypoint_lane_id'))
        if k in lane_ids:governs.add(lane_ids[k])
    for native_key in attrs.get('observed_governs',[]):
        key_tuple=tuple(native_key)
        if key_tuple not in lane_ids:raise ValueError('Native governed lane missing from map')
        governs.add(lane_ids[key_tuple])
    if governs:record['governs']=sorted(governs)
    # mayAffect is not proof of device governance.
    if kind=='traffic_signal':
        state=str(attrs.get('light_state','')).split('.')[-1]
        indication={'Red':'circular_red','Yellow':'circular_yellow','Green':'circular_green','Off':'dark'}.get(state)
        if indication:record['indications']=[indication]
    if kind=='speed_limit_sign' and 'landmark_value' in attrs:
        unit=str(attrs.get('landmark_unit','')).lower()
        factor={'km/h':1/3.6,'mph':.44704,'m/s':1}.get(unit)
        if factor is not None:
            record.update(speed_value=float(attrs['landmark_value'])*factor,speed_kind='maximum')
    return key,record


def observed_inoperative(indications, uncovered=None):
    """Installed signal operability: darkness alone does not prove uncovered."""
    if any(v in ('circular_red','circular_yellow','circular_green')for v in indications or []):return False
    if indications==['dark'] and uncovered is not None:return uncovered
    return None


def recorded_traffic_props(text):
    """Initial static traffic-prop identities/positions; recorder units are cm.

    These point observations establish existence, not a physical footprint. Raw
    graph body geometry replaces them when observed; otherwise occupancy is unknown.
    """
    initial=re.split(r'\nFrame 2\b',text,maxsplit=1)[0]
    result={}
    pattern=r'Create (\d+): (static\.prop\.[^ ]+) \([^)]*\) at \(([^)]+)\)'
    for actor,blueprint,location in re.findall(pattern,initial):
        if not any(word in blueprint for word in ('barrier','trafficcone')):continue
        position=[float(v.strip())/100 for v in location.split(',')]
        result[int(actor)]={'kind':'obstruction','position':xy(position)}
    return result


def verify_join(evidence, telemetry, frames):
    if not evidence:raise ValueError('Empty capture')
    tmap={r['frame']:r for r in telemetry}; fmap={r['frame']:r for r in frames}
    if len(tmap)!=len(telemetry) or len(fmap)!=len(frames):raise ValueError('Duplicate source frame')
    last=-1;seen=set();actor=evidence[0]['actor_id'];previous=None
    for e in evidence:
        if e['original_frame'] in seen:raise ValueError('Duplicate evidence frame')
        seen.add(e['original_frame'])
        if e['actor_id']!=actor:raise ValueError('Subject identity changed')
        if previous is not None and (e['original_frame']<=previous['original_frame'] or e['replay_frame']<=previous['replay_frame']):
            raise ValueError('Frame identities must increase')
        previous=e
        t=round(e['recording_time_s']*1000)
        if t<=last:raise ValueError('Millisecond timestamps must strictly increase')
        last=t
        if e['original_frame'] not in tmap or e['replay_frame'] not in fmap:raise ValueError('Missing frame join')
        row=tmap[e['original_frame']]
        if abs(row['time_s']-e['recording_time_s'])>1e-6:raise ValueError('Original timestamp mismatch')
        if abs(fmap[e['replay_frame']]['simulation_time']-e['replay_simulation_time_s'])>1e-6:raise ValueError('Replay timestamp mismatch')
        if e['ego'].get('speed_provenance')!='original_trace_actor_get_velocity':raise ValueError('Untrusted original speed provenance')
        if abs(e['ego']['speed_mps']-row['speed_mph']*.44704)>1e-6:raise ValueError('Observed speed mismatch')
        if any(abs(a-b)>.001 for a,b in zip(e['ego']['position_m'],row['position_m'])):raise ValueError('Pose join mismatch')
    return tmap,fmap


def validate_scene(scene):
    users=[u['track'] for u in scene['users']]; regions=[s['id'] for s in scene['structures']]
    devices=[d['id'] for d in scene['devices']]
    if scene['subject'] not in users or len(users)!=len(set(users)):raise ValueError('Invalid subject/user identity')
    if len(regions)!=len(set(regions)) or len(devices)!=len(set(devices)):raise ValueError('Duplicate map identity')
    if any(t not in users or r not in regions for t,r in scene.get('occupies',[])):raise ValueError('Dangling occupancy')
    if any(r not in regions for d in scene['devices'] for r in d.get('governs',[])):raise ValueError('Dangling governs')
    if any(r['a'] not in users or r['b'] not in users for r in scene.get('relations',[])):raise ValueError('Dangling relation')
    rounded(scene)


def convert(capture, original, library, output):
    """Convert once into a new directory; preserve all source evidence unchanged."""
    capture,original,library,output=map(lambda p:Path(p).resolve(),(capture,original,library,output))
    evidence=rows(capture/'evidence.jsonl'); telemetry=rows(original/'trace.jsonl');frames=rows(capture/'native/frames.jsonl')
    tmap,fmap=verify_join(evidence,telemetry,frames)
    source_manifest=json.loads((capture/'manifest.json').read_text())
    acquisition=source_manifest.get('acquisition')
    physical_registry=None
    if source_manifest.get('physical_actor_registry'):
        from .physical_actors import load_registry,validate_frame
        ref=source_manifest['physical_actor_registry'];path=capture/ref['path']
        if sha(path)!=ref['sha256']:raise ValueError('Physical registry source hash mismatch')
        physical_registry=load_registry(path)
        for event in evidence:validate_frame(event['original_observations']['participants'],physical_registry)
    elif any(a.get('physical_classification') for e in evidence for a in e.get('original_observations',{}).get('participants',[])):
        raise ValueError('Unbound physical actor classification')
    if source_manifest.get('observation_contract_version'):
        offset=evidence[0]['replay_simulation_time_s']-evidence[0]['recording_time_s']
        for i,row in enumerate(evidence):
            if abs(row['replay_simulation_time_s']-row['recording_time_s']-offset)>1e-5:
                raise ValueError('Declared trace time diverges from the original simulation clock')
            if i and row['original_frame']!=evidence[i-1]['original_frame']+1:
                raise ValueError('Original mandatory per-tick capture omitted a frame')
    participant_path=original/'synchronized_motion_records.jsonl'
    participant_records=original_participants(participant_path,evidence,acquisition)
    if source_manifest.get('extraction_confirmed') is not True:raise ValueError('Capture extraction unconfirmed')
    if source_manifest.get('frames')!=len(evidence) or len(evidence)!=len(telemetry) or len(evidence)!=len(frames):
        raise ValueError('Capture/telemetry/frame counts differ; refusing to drop frames')
    for name in ('road.xodr','trace.jsonl'):
        if sha(original/name)!=source_manifest['sources'][name]:raise ValueError('Source hash mismatch: '+name)
    junction_report=[]
    native_facts={}
    if source_manifest.get('native_map_facts'):
        facts_path=capture/source_manifest['native_map_facts']['path']
        if sha(facts_path)!=source_manifest['native_map_facts']['sha256']:raise ValueError('Native map facts hash mismatch')
        native_facts=json.loads(facts_path.read_text())
    from .inventory_observations import observations as inventory_observations, project as project_inventory
    inventory_records = inventory_observations(original, telemetry, native_facts,
                                               source_manifest.get('required_observations', []))
    inventory_projection = {atom: [] for atom in inventory_records}
    configuration=json.loads((original/'config.json').read_text()) if (original/'config.json').exists() else {}
    public_way_roads=configuration.get('public_way_road_ids',[])
    projection_public_way_roads=public_way_roads
    diagnostic_public_way_projection=False
    if public_way_roads:
        values=dict(configuration.get('authored_test_context',{}).get('core_assumptions',[]))
        if values.get('asm.public_highway') is not True:raise ValueError('Public-way regions need an explicit administrative assumption')
        if any(e.get('original_observations',{}).get('map_context',{}).get('declared_public_way_road_ids')!=public_way_roads for e in evidence):
            # Compatibility recipes retain a small, pinned speed capture while
            # materializing the exact case configuration. Its road inventory is
            # necessarily smaller than an intersection case's native map. Use
            # the recorded road roles only when every identifying source is
            # byte-for-byte the shipped diagnostic fixture. Native captures
            # still require exact agreement with their original observations.
            base=Path(__file__).resolve().parents[2]/'fixtures/retained-speed'
            markers=('fixture-provenance.json','road.xodr','trace.jsonl','capture/evidence.jsonl')
            if not all((original/name).is_file() and (base/name).is_file() and
                       sha(original/name)==sha(base/name) for name in markers):
                raise ValueError('Public-way role declaration differs from original graph observations')
            recorded=[e.get('original_observations',{}).get('map_context',{}).get('declared_public_way_road_ids') for e in evidence]
            if not recorded[0] or any(roads!=recorded[0] for roads in recorded):
                raise ValueError('Diagnostic public-way road observations differ across frames')
            projection_public_way_roads=recorded[0]
            diagnostic_public_way_projection=True
    regions,polygons,lane_ids=static_map(original/'road.xodr',junctions=True,junction_report=junction_report,
                                      native_junction_boxes=native_facts.get('junctions',[]),
                                      include_non_driving=bool(source_manifest.get('observation_contract_version')),public_way_roads=projection_public_way_roads)
    from .native_control_observations import read_observations as native_control_observations
    inventory_records.update(native_control_observations(original,telemetry,lane_ids,regions,
        source_manifest.get('required_observations', [])))
    inventory_projection = {atom: [] for atom in inventory_records}
    from .native_road_profile import apply as apply_native_road_profile
    native_road_profile = apply_native_road_profile(original,telemetry,regions,polygons)
    painted=painted_map_objects(original/'road.xodr')
    for observation in painted:
        region=observation['region'];region['id']=len(regions)+1
        regions.append(region);polygons[region['id']]=observation['shape']
    centre_lines=native_centre_lines(original/'road.xodr')
    for observation in centre_lines:
        region=observation['region'];region['id']=len(regions)+1
        regions.append(region);polygons[region['id']]=observation['shape']
    # Recorded creation events establish ego class independently of cell/law text.
    recorder=(capture/'recorder_info.txt').read_text()
    blueprint=re.search(r'Create '+str(evidence[0]['actor_id'])+r': ([^ ]+)',recorder)
    if not blueprint:raise ValueError('Recorded subject blueprint unavailable')
    ego_classes,unknown_classes=classes(blueprint.group(1),library)
    if ego_classes is None:raise ValueError('Unclassifiable subject')
    times=[e['recording_time_s'] for e in evidence]
    yaw=rates(times,[e['ego']['heading_deg'] for e in evidence])
    marking_sets={}; obstacles=recorded_traffic_props(recorder); raw_keys=set(); raw_hashes={}; devices={}
    # Scan raw map/prop observations before emitting scenes: static objects repeat.
    for e in evidence:
        path=capture/'native'/fmap[e['replay_frame']]['base']
        if not path.is_file():raise ValueError('Raw graph missing: '+str(path))
        graph=load_graph(path);raw_hashes[e['replay_frame']]=sha(path)
        if graph.graph.get('frame')!=e['replay_frame']:raise ValueError('Raw graph frame mismatch')
        for node,a in graph.nodes(data=True):
            raw_keys.update(a)
            if 'waypoint_lane_id' in a:
                key=(a['waypoint_road_id'],a['waypoint_section_id'],a['waypoint_lane_id'])
                for side in ('left','right'):
                    value=(a.get(side+'_lane_marking_type'),a.get(side+'_lane_marking_color'))
                    marking_sets.setdefault((key,side),set()).add(value)
            device_key,device=device_record(node,a,graph,lane_ids)
            if device_key is not None:
                static={k:v for k,v in device.items() if k!='indications'}
                if device_key in devices:
                    old=devices[device_key]
                    old['governs']=sorted(set(old.get('governs',[]))|set(static.get('governs',[])))
                else:devices[device_key]=static
            sem=a.get('sem_class','')
            if sem.startswith('static.prop.') and any(word in sem for word in ('barrier','trafficcone')) and 'threedbbox' in a:
                aid=a.get('carla_id',a.get('entity_id'))
                if aid is None:raise ValueError('Static prop has no stable identity')
                vertices=a['threedbbox'].tolist() if hasattr(a['threedbbox'],'tolist') else a['threedbbox']
                _,_,polygon=body(vertices,0)
                boundary=[list(v) for v in polygon.exterior.coords[:-1]]
                if aid in obstacles and 'boundary' in obstacles[aid] and obstacles[aid]['boundary']!=boundary:raise ValueError('Static prop moved')
                obstacles[aid]={'kind':'obstruction','boundary':boundary,'position':xy(a['vertex'])}
    marking_types={'Broken':'broken','Solid':'solid','SolidSolid':'double_solid','BottsDots':'dotted','Curb':'curb','NONE':'none','None':'none'}
    for (key,side),values in marking_sets.items():
        if key in lane_ids and len(values)==1:
            typ,col=next(iter(values))
            if typ in marking_types and col in ('White','Yellow'):
                next(r for r in regions if r['id']==lane_ids[key])['lane']['marking_'+side]=[marking_types[typ],col.lower()]
    from shapely.geometry import Polygon
    for aid,region in sorted(obstacles.items()):
        region['id']=len(regions)+1;regions.append(region)
        if 'boundary' in region:polygons[region['id']]=Polygon(region['boundary'])
    from .control_portions import apply as apply_authored_control_portions
    control_portions=apply_authored_control_portions(original,regions,polygons,lane_ids,devices)
    from .scenario_geometry import apply as apply_scenario_geometry
    scenario_geometry=apply_scenario_geometry(original,regions,polygons,devices)
    for ident,key in enumerate(sorted(devices),1):devices[key]['id']=ident
    output.mkdir(parents=True,exist_ok=False)
    source_paths={'capture_evidence':capture/'evidence.jsonl','frame_index':capture/'native/frames.jsonl','original_telemetry':original/'trace.jsonl','map':original/'road.xodr','recorder_info':capture/'recorder_info.txt','capture_manifest':capture/'manifest.json'}
    if control_portions:source_paths['authored_control_config']=original/'config.json'
    if scenario_geometry:
        source_paths['scenario_geometry']=original/'scenario_geometry.json'
        if (original/'scenario_rule_evidence.jsonl').exists():source_paths['scenario_rule_evidence']=original/'scenario_rule_evidence.jsonl'
    from .environment_measurements import load as load_environment, project as project_environment
    environment_packet=load_environment(original)
    if environment_packet:
        source_paths['environment_calibration']=original/'environment_calibration.json'
        source_paths['authored_surface_provenance']=original/'surface_provenance.json'
    if participant_records:source_paths['original_participant_telemetry']=participant_path
    if native_facts:
        source_paths['native_map_facts']=facts_path
    report={'status':'draft','adapter':VERSION,'frames':len(evidence),'inputs':{k:{'path':str(p),'sha256':sha(p)} for k,p in source_paths.items()},
            'diagnostic_public_way_projection':diagnostic_public_way_projection,
            'full_core':str(full_core(library)), 'subject_blueprint':blueprint.group(1),
            'native_junction_mapping':junction_report,
            'authored_speed_control_portions':control_portions,
            'scenario_geometry_projection':scenario_geometry,
            'native_road_profile_projection':native_road_profile,
            'native_painted_objects':[dict(o['source'],region_id=o['region']['id']) for o in painted],
            'native_centre_lines':[dict(o['source'],region_id=o['region']['id'])for o in centre_lines],
            'adapter_sources':{p.name:sha(p) for p in (Path(__file__).parent/'adapter.py',Path(__file__).parent/'geometry.py',Path(__file__).parent/'control_portions.py',Path(__file__).parent/'scenario_geometry.py',Path(__file__).parent/'inventory_observations.py')},
            'methods':{'position':'body centre from recorded bounding-box vertices; CARLA y reflected',
                       'speed':'original live telemetry; mph multiplied by 0.44704',
                       'participant_motion':'original same-frame actor.get_velocity and body telemetry, including measured actors outside the graph crop; no visibility inferred' if participant_records else ('original live graph actor.get_velocity only' if acquisition=='original_live_run' else 'replay motion omitted; unknown'),
                       'yaw_rate':'unwrapped reflected heading; central/one-sided finite difference; degrees/s; subject-only estimate',
                       'path_length':'trapezoidal integration of original speed; gaps leave unknown',
                       'occupancy':'recorded convex body footprint intersects 2 m sampled OpenDRIVE lane/roadway polygons',
                       'sight_distance':'per-frame minimum clear-side any-body horizon over all required road lanes, attached to ego-overlapping lane/roadway regions; detailed evidence retained',
                       'weather':'darkness: sun altitude < 0; precipitation/wetness: parameter > 0; classifications are estimates'},
            'limitations':(['Pinned retained-speed diagnostic capture projects only its recorded public-way roads; exact-case native road roles remain unverified.'] if diagnostic_public_way_projection else [])+['Sight distance is a subject-relative sampled lower bound for the 500 ft test, not an exact or uncensored cutoff. rel.visible requires separate original subject-to-user body rays; older centre-only captures remain unknown.',
                           'No observed signal-off enum; absent ego lamps are not inferred from controller signals.',
                           'Normalized steering control is not wheel angle; commanded gear is not observed gear.',
                           'Core device.governs is a non-optional list: it cannot distinguish unobserved governance from an empty list. Retain observed edges and report incomplete device coverage; no compliance conclusion follows.',
                           'Curved lanes have no single direction vector; lane direction omitted there.',
                           'Recorder-only traffic props establish existence/position but not a boundary; incomplete geometry leaves occupancy unknown because Core has no per-region observation mask.',
                           'Only captured/map-supported entities are emitted. Required crosswalk inventories lacking complete same-frame evidence retain Core unobserved_kinds; verified absence requires original hash-bound renderer and marked/unmarked region receipts. Native-map emptiness is insufficient. Other empty inventory families remain unsupported.',
                           'OpenDRIVE line/arc geometry only; unsupported geometry fails conversion.',
                           'Reference curvature is attached to local roadway patches, not to the full lane.'],
            'structures_without_observed_boundary':[r['id'] for r in regions if 'boundary' not in r],
            'occupancy_complete':len(polygons)==len(regions),
            'raw_attribute_keys':sorted(raw_keys),'supplementary_evidence':'supplementary_evidence.jsonl',
            'production_contract':source_manifest.get('observation_contract_version'),
            'visibility_frames_with_scalar':0, 'visibility_frames_without_scalar':0,
            'visibility_missing_reasons':{}, 'decoder_validation':'not_run'}
    period=sorted(times[i]-times[i-1] for i in range(1,len(times)))[(len(times)-1)//2] if len(times)>1 else 0
    travelled=0.;gapped=False
    from authored_context import assumptions
    authored_config_path = original/'config.json'
    authored_configuration = json.loads(authored_config_path.read_text()) if authored_config_path.exists() else {}
    authored_assumptions=assumptions(authored_configuration.get('authored_test_context',{}))
    with (output/'trace.json').open('w') as out,(output/'supplementary_evidence.jsonl').open('w') as extra:
        out.write('{"scenes":[')
        for i,e in enumerate(evidence):
            row=tmap[e['original_frame']]; graph_path=capture/'native'/fmap[e['replay_frame']]['base'];graph=load_graph(graph_path)
            if i:
                dt=times[i]-times[i-1]
                if dt>period*1.5:gapped=True
                travelled+=dt*(evidence[i-1]['ego']['speed_mps']+e['ego']['speed_mps'])/2
            centre,extent,footprint=body(e['ego']['body_vertices_m'],e['ego']['heading_deg'])
            h=math.radians(-e['ego']['heading_deg'])
            kin={'position':centre,'heading':[math.cos(h),math.sin(h)],'speed':e['ego']['speed_mps'],'extent':extent}
            if 'velocity_mps' in row:
                kin['velocity']=xy(row['velocity_mps'])
            if yaw[i] is not None:kin['yaw_rate']=yaw[i]
            if not gapped:kin['path_length']=travelled
            for old,new in [('throttle','throttle'),('brake','service_brake'),('hand_brake','parking_brake')]:
                if old in row['control']:kin[new]=row['control'][old]
            if 'accel_longitudinal_mps2' in row:kin['accel_longitudinal']=row['accel_longitudinal_mps2']
            if 'wheel_steer_angle_deg' in row:kin['steer_angle']=-row['wheel_steer_angle_deg']
            users=[{'track':e['actor_id'],'classes':ego_classes,'unobserved_classes':unknown_classes,'kin':kin}]
            footprints={e['actor_id']:footprint}
            current_devices={key:dict(value) for key,value in devices.items()}
            for node,a in graph.nodes(data=True):
                key,device=device_record(node,a,graph,lane_ids)
                if key is not None and 'indications' in device:current_devices[key]['indications']=device['indications']
                if key is not None and device.get('kind')=='traffic_signal':
                    if source_manifest.get('observation_contract_version'):
                        # Current native capture does not observe head coverings.
                        # An authored declaration cannot fill that observation.
                        value=observed_inoperative(device.get('indications'))
                        if value is not None:current_devices[key]['inoperative']=value
                    elif device.get('indications')==['dark']:current_devices[key]['inoperative']=True
                if not source_manifest.get('observation_contract_version') and key is not None and scenario_geometry and key[0]=='actor' and int(key[1]) in scenario_geometry['declaration'].get('inoperative_signal_actor_ids',[]):
                    if scenario_geometry['declaration'].get('signal_heads_uncovered') is True:current_devices[key]['uncovered']=True
                if node=='ego':
                    observed_signals=signals(a)
                    if observed_signals:users[0]['sig']=observed_signals
                sem=a.get('sem_class','')
                if not sem.startswith(('vehicle.','walker.')):continue
                aid=a.get('carla_id',a.get('entity_id'))
                if aid is None or aid<0:raise ValueError('Road user has no natural stable ID')
                if aid==e['actor_id']:continue
                found,unknown=classes(sem,library)
                u={'track':aid,'classes':found,'unobserved_classes':unknown,'kin':{}}
                u['kin'].update(live_kinematics(a,acquisition))
                if 'vertex' in a:u['kin']['position']=xy(a['vertex'])
                if 'forward' in a:u['kin']['heading']=xy(a['forward'])
                if 'threedbbox' in a:
                    head=math.degrees(math.atan2(a['forward'][1],a['forward'][0]))
                    c,ex,p=body(a['threedbbox'],head);u['kin'].update(position=c,extent=ex);footprints[aid]=p
                observed_signals=signals(a)
                if observed_signals:u['sig']=observed_signals
                users.append(u)
            measured = e.get('original_observations')
            if measured:
                if measured['frame'] != e['original_frame'] or abs(measured['time_s'] - e['recording_time_s']) > 1e-6:
                    raise ValueError('Original observation packet does not join frame')
                if graph.graph.get('observed_evidence') != measured:
                    raise ValueError('Raw graph lost original observation packet')
                actors = {a['actor_id']:a for a in measured['participants']}
                if len(actors) != len(measured['participants']):raise ValueError('Duplicate observed actor')
                attach_original_participants(users,footprints,actors,e['actor_id'],library)
                for user in users:
                    actor=actors.get(user['track'])
                    if actor:
                        user['kin']['accel_longitudinal']=actor['accel_longitudinal_mps2']
                        found,unknown=classes(actor['blueprint'],library,actor.get('blueprint_attributes'),actor.get('physical_classification'))
                        user['classes']=found;user['unobserved_classes']=unknown
                        lamps=signals(actor.get('light_attributes',{}))
                        if lamps:user.setdefault('sig',{}).update(lamps)
            attach_original_participants(users,footprints,participant_records.get(e['original_frame'],{}),e['actor_id'],library)
            weather=e['world'].get('weather',{});env={}
            for key,target,test in [('sun_altitude_angle','darkness',lambda v:v<0),('precipitation','precipitation',lambda v:v>0),('wetness','wet_road',lambda v:v>0)]:
                if key in weather:env[target]=test(weather[key])
            measured_environment, environmental_mapping=project_environment(environment_packet,row,e['original_frame'])
            env.update(measured_environment)
            structures, visibility_mapping = attach_visibility(regions, polygons, footprint, e.get('visibility'))
            if visibility_mapping['value_m'] is None:
                report['visibility_frames_without_scalar'] += 1
                reason = visibility_mapping['reason']
                report['visibility_missing_reasons'][reason] = report['visibility_missing_reasons'].get(reason, 0)+1
            else:
                report['visibility_frames_with_scalar'] += 1
            scene={'t':round(times[i]*1000),'subject':e['actor_id'],'users':users,'structures':structures,'devices':list(current_devices.values()),
                   'occupancy_observed':list(footprints) if len(polygons)==len(regions) else [],'occupies':[[aid,rid] for aid,p in footprints.items() for rid,poly in polygons.items() if p.intersects(poly)],'env':env,'links':[]}
            if measured:
                relations = [{k:r[k] for k in ('a','b','visible')} for r in measured.get('relations',[])]
                if relations:scene['relations']=relations
            if authored_assumptions:scene['assumptions']=authored_assumptions
            inventory_frame = project_inventory(scene, inventory_records, i)
            for atom, record in inventory_frame.items():inventory_projection[atom].append(record)
            validate_scene(scene)
            if i:out.write(',')
            json.dump(serialized_scene(scene,bool(source_manifest.get('observation_contract_version'))),out,separators=(',',':'),allow_nan=False)
            # Full records, no field filtering. Raw graph remains immutable and
            # hash-addressed; no source concept is silently lost by the adapter.
            extra.write(json.dumps({'evidence':e,'original_telemetry':row,'original_participants':participant_records.get(e['original_frame'],{}),'raw_graph':{'path':str(graph_path),'sha256':raw_hashes[e['replay_frame']]},'world_scene_t':scene['t'],'visibility_mapping':visibility_mapping,'environmental_mapping':environmental_mapping},separators=(',',':'),allow_nan=False)+'\n')
        out.write(']}\n')
    required = set(source_manifest.get('required_observations', []))
    capability = manifest(library,acquisition=='original_live_run',report['visibility_frames_with_scalar'] > 0,
        extended_observations=bool(source_manifest.get('observation_contract_version')),
        road_user_visibility=source_manifest.get('road_user_visibility_observed',False),
        wheel_angles=bool(telemetry) and all('wheel_steer_angle_deg' in row for row in telemetry))
    if physical_registry:
        if 'ru.animal' not in capability['atoms']:raise ValueError('Registered animal needs isolated versioned Animal ontology')
        capability['atoms']['ru.animal']='estimate:hash_bound_genuine_cooked_mesh_physical_class'
        report['physical_animal_projection']={'registry_sha256':physical_registry['sha256'],'actor_ids':list(physical_registry['actors']),'frames':len(evidence),'scope':'Genuine physical Cow class only; no legal herding, due-regard or compliance judgment'}
    if environment_packet:
        capability['atoms']['env.visibility']='estimate:rendered_target_contrast_range_with_retained_censoring'
        capability['atoms']['env.ice_or_snow']='estimate:hash_bound_authored_native_surface'
        report['environmental_measurement_projection']={'calibration_sha256':environment_packet['calibration_sha256'],'surface_sha256':environment_packet['surface_sha256'],'frames':report['frames'],'visibility_distance_kind':environment_packet['calibration']['distance_kind']}
    if native_road_profile:
        capability['atoms']['st.crest']='estimate:surveyed_native_elevation_maximum_mesh_ridge'
        capability['atoms']['st.grade']='estimate:surveyed_native_two_metre_midpoint_grade_patches'
    if public_way_roads:capability['atoms']['st.highway']='estimate:native_full_way_geometry_under_recorded_public_assumption'
    for kind in {r['kind'] for r in regions}:
        atom='st.'+kind
        if atom in capability['atoms'] and capability['atoms'][atom]=='absent' and scenario_geometry:
            capability['atoms'][atom]='estimate:verified_authored_region_role'
    if scenario_geometry and scenario_geometry['declaration'].get('direction_sign_objects'):
        capability['atoms']['dev.regulatory_sign']='estimate:original_frame_verified_authored_direction_sign'
    if source_manifest.get('observation_contract_version'):
        from .atom_contract import inventory, required_coverage
        contract=inventory(library,capability['atoms'])
        # Conversion already retains all original frames. A separate atom audit
        # validates required values, not only presence in a capability manifest.
        scenes=json.loads((output/'trace.json').read_text())['scenes']
        coverage=required_coverage(required,capability,scenes,inventory_projection)
        report['atom_coverage']=coverage
        report['required_measurements_complete']=coverage['passed']
        (output/'atom_contract.json').write_text(json.dumps(contract,indent=2)+'\n')
    else:
        report['required_measurements_complete'] = (
            ('st.sight_distance' not in required or report['visibility_frames_with_scalar'] == report['frames']) and
            ('rel.occupies' not in required or report['occupancy_complete']))
    report['inventory_observations'] = inventory_projection
    if inventory_projection:
        inventory_path = output/'inventory_observations.json'
        inventory_path.write_text(json.dumps(inventory_projection,indent=2,allow_nan=False)+'\n')
        report['inventory_observation_receipt'] = {'path':str(inventory_path),'sha256':sha(inventory_path)}
    report['required_observations'] = sorted(required)
    for name,data in [('manifest.json',capability),('adapter_report.json',report)]:
        (output/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    return report
