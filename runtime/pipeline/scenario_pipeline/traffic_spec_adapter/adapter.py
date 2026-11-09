"""Convert a raw recorded capture into TrafficSpec's runtime data, without laws.

Native replay kinematics are not original telemetry. Incoming virtual-observer
rays supply a disclosed, subject-relative regional sight-distance estimate, not rel.visible. Supplementary output retains every
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

VERSION = 'traffic-spec-source-capabilities'

# Every current ontology atom needs an explicit acquisition decision.  This is
# deliberately exhaustive: adding an atom to Core cannot silently turn it into
# an unsupported capability through a dictionary default.
UNSUPPORTED_ATOMS = frozenset('''
dev.crossing_warning_signal dev.human_direction dev.pedestrian_signal
dev.railway_signal_or_gate dev.school_bus_signal dev.speed_limit_beacon
dev.temporary_traffic_control dev.zone_sign env.civil_time kin.engine_running kin.gear
ru.commercial_motor_vehicle ru.electric_bicycle ru.electric_scooter ru.emergency_vehicle
ru.fire_apparatus ru.moped ru.occupant_count ru.official_vehicle
ru.pedestrian_with_white_cane_or_guide_animal ru.rail_vehicle ru.rider_posture ru.school_bus
ru.taxicab ru.tour_bus_or_limousine ru.trailer_or_combination ru.transit_bus
sig.compression_brake sig.door_open sig.hand_signal sig.horn sig.siren sig.warning_lamp
st.alley st.centre_turn_lane st.controlled_access st.curb_zone
st.driveway_or_alley_entrance st.elevated_structure st.fire_hydrant st.fire_station_entrance
st.parking_space st.pedestrian_grade_separation st.railway_crossing st.reserved_lane
st.road_edge st.roundabout st.safety_zone st.sight_along_way st.transit_stop
st.travel_region st.turn_lane
'''.split())


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


def check_json(value):
    """Validate measurements without allocating and rounding a discarded copy."""
    if value is None or isinstance(value,(str,bool,int)):return
    if isinstance(value,float):
        if not math.isfinite(value):raise ValueError('Nonfinite measurement')
        return
    if isinstance(value,dict):values=value.values()
    elif isinstance(value,(tuple,list)):values=value
    else:raise ValueError('Unsupported JSON value '+str(type(value)))
    for item in values:check_json(item)


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


def manifest(library):
    """Capability of this recorded-capture adapter, not presence in one scene.

    Unsupported atoms are enumerated explicitly. Per-frame omissions remain
    unknown even for a supported capability. Curved lanes lack a single global
    direction. A source capability does not assert that every physical mark in
    a scene has a resolved association.
    """
    observed={'ru.subject':'exact','ru.aggregate':'exact','ru.motor_vehicle':'exact',
              'ru.pedestrian':'exact','ru.bicycle':'estimate:blueprint_classification',
              'ru.motorcycle':'estimate:blueprint_classification',
              'kin.time':'exact','kin.position':'exact','kin.heading':'exact','kin.extent':'exact',
              'kin.speed':'exact',
              'kin.velocity':'exact',
              'kin.yaw_rate':'estimate:timestamped_unwrapped_heading_difference','kin.path_length':'subject',
              'kin.throttle':'subject','kin.service_brake':'subject','kin.parking_brake':'subject',
              'st.lane':'exact','st.roadway':'exact','st.lane_direction':'estimate:local_native_heading_or_sampled_chord',
              'st.lane_adjacency':'exact','st.lane_width':'exact',
              'st.lane_marking':'exact','st.curvature':'exact','st.grade':'exact',
              'st.intersection':'estimate:native_junction_geometry',
              'st.centre_line':'estimate:native_opposing_lane_divider',
              'st.lane_enters':'exact',
              'st.stop_line':'estimate:native_or_measured_constructed_paint',
              'st.crosswalk':'estimate:native_map_or_measured_constructed_region',
              'st.bicycle_lane_or_path':'estimate:complete_native_lane_and_verified_facility_inventory',
              'dev.lane_control_signal':'estimate:complete_native_control_and_verified_source_asset_inventory',
              'st.region_geometry':'estimate:sampled_map_and_recorded_body_geometry',
              'st.obstruction':'estimate:recorded_traffic_prop',
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
    # Implemented source-wide acquisition paths; frame coverage is separate.
    observed['kin.accel_longitudinal'] = 'exact'
    observed['ru.bus'] = 'estimate:recorded_native_blueprint_base_type'
    observed['ru.truck'] = 'estimate:recorded_native_blueprint_base_type'
    observed['ru.child'] = 'estimate:walker_age_or_observed_nonpedestrian_classification'
    observed['st.sidewalk'] = 'estimate:native_lane_surface_role'
    observed['st.shoulder'] = 'estimate:native_lane_surface_role'
    observed['st.lane_connectivity'] = 'estimate:native_lane_links_or_verified_unique_road_continuation'
    observed.update({
        'kin.steer_angle':'subject', 'rel.visible':'subject',
        'st.entrance_of':'estimate:recorded_control_and_map_topology_join',
        'st.highway':'estimate:verified_public_map_surface_envelope',
        'st.on_way':'estimate:verified_native_road_identity_and_continuation',
        'dev.inoperative':'estimate:valid_observed_native_indication_excludes_inoperability',
        'st.median_or_divider':'estimate:verified_physical_region_role',
        'st.one_way_roadway':'estimate:verified_physical_region_role',
        'dev.regulatory_sign':'estimate:verified_physical_sign_legend',
        'env.visibility':'estimate:retained_rendered_contrast_calibration',
        'env.ice_or_snow':'estimate:verified_native_surface',
        'st.crest':'estimate:surveyed_native_elevation',
        'st.sight_distance':'estimate:incoming_virtual_observer_to_subject_body',
    })
    ids=atom_ids(library)
    if not ids:raise ValueError('No ontology atom IDs found')
    if set(observed)&UNSUPPORTED_ATOMS:raise ValueError('Acquisition atom declared both observed and unsupported')
    if (set(observed)|UNSUPPORTED_ATOMS)-set(ids):raise ValueError('Acquisition table contains a retired atom')
    if set(ids)-(set(observed)|UNSUPPORTED_ATOMS):
        raise ValueError('Ontology atom lacks an explicit acquisition decision: '+str(sorted(set(ids)-(set(observed)|UNSUPPORTED_ATOMS))))
    return {'source':VERSION,'reid_gap':0,'atoms':{k:observed[k] if k in observed else 'absent' for k in ids if k != 'sig.hand_signal'}}

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
    mask=attrs.get('vehicle_light_state')
    if type(mask) is int and mask>=0:
        attrs=dict(attrs)
        for source,bit in LAMP_BITS.items():
            if attrs.get(source) is None:attrs[source]=bool(mask & bit)
    for source,target in [('light_Brake','brake_lamp'),('light_Position','position_lamp'),('light_Reverse','reverse_lamp')]:
        if attrs.get(source) is not None:result[target]=bool(attrs[source])
    if attrs.get('light_LeftBlinker') is not None and attrs.get('light_RightBlinker') is not None:
        left,right=bool(attrs['light_LeftBlinker']),bool(attrs['light_RightBlinker'])
        result['hazard']=left and right
        if left!=right:result['turn_indicator']='left' if left else 'right'
        elif not left:result['turn_indicator']='off'
        # Hazard is separate; both enabled does not select a turn side.
    if attrs.get('light_HighBeam') is not None and attrs.get('light_LowBeam') is not None:
        result['headlamp']='high_beam' if attrs['light_HighBeam'] else ('low_beam' if attrs['light_LowBeam'] else 'off')
    return result


def merge_device_governance(existing, observation):
    """Accumulate observed targets without converting unknown to observed none."""
    if 'governs' in existing or 'governs' in observation:
        existing['governs']=sorted(set(existing.get('governs',[]))|set(observation.get('governs',[])))


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
    observed_governs=attrs.get('observed_governs')
    if observed_governs is not None and not isinstance(observed_governs,list):
        raise ValueError('Observed governance must be a list or unknown')
    for native_key in observed_governs or []:
        key_tuple=tuple(native_key)
        if key_tuple not in lane_ids:raise ValueError('Native governed lane missing from map')
        governs.add(lane_ids[key_tuple])
    if governs or observed_governs is not None:record['governs']=sorted(governs)
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



def project_operability(devices):
    """A valid observed indication proves the head is not inoperative.

    Darkness or a missing indication cannot establish installation/uncovering.
    Those values remain omitted; no false/off default is introduced.
    """
    from collections import Counter
    changes=Counter()
    for device in devices:
        if device.get('kind')!='traffic_signal':continue
        value=observed_inoperative(device.get('indications'))
        if value is None:
            if 'inoperative' in device:device.pop('inoperative');changes['unverified_operability_made_unknown']+=1
        elif device.get('inoperative') is not value:
            device['inoperative']=value;changes['measured_non_inoperative_signal']+=1
    return changes


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


def verify_join(evidence, telemetry, frames, *, diagnostic_fixture=False):
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
        speed_source=e['ego'].get('speed_provenance')
        if speed_source!='original_trace_actor_get_velocity' and not (diagnostic_fixture and speed_source=='synthetic_native_sample'):
            raise ValueError('Untrusted original speed provenance')
        if abs(e['ego']['speed_mps']-row['speed_mph']*.44704)>1e-6:raise ValueError('Observed speed mismatch')
        if any(abs(a-b)>.001 for a,b in zip(e['ego']['position_m'],row['position_m'])):raise ValueError('Pose join mismatch')
    return tmap,fmap


def validate_scene(scene, library=None, *, check_numbers=True):
    users=[u['track'] for u in scene['users']]; regions=[s['id'] for s in scene['structures']]
    devices=[d['id'] for d in scene['devices']]
    if scene['subject'] not in users or len(users)!=len(set(users)):raise ValueError('Invalid subject/user identity')
    if len(regions)!=len(set(regions)) or len(devices)!=len(set(devices)):raise ValueError('Duplicate map identity')
    if any(t not in users or r not in regions for t,r in scene.get('occupies',[])):raise ValueError('Dangling occupancy')
    if any(r not in regions for d in scene['devices'] for r in d.get('governs',[])):raise ValueError('Dangling governs')
    if any(r['a'] not in users or r['b'] not in users for r in scene.get('relations',[])):raise ValueError('Dangling relation')
    from intentions import validate_scene_intents
    if library is not None:
        from .trace_contract import validate as validate_fields
        validate_fields(scene, library)
    from .compatibility import validate as validate_compatibility
    validate_scene_intents(scene)
    validate_compatibility(scene)
    if check_numbers:check_json(scene)


def convert(capture, original, library, output, *, diagnostic_fixture=False):
    """Convert once into a new directory; preserve all source evidence unchanged."""
    capture,original,library,output=map(lambda p:Path(p).resolve(),(capture,original,library,output))
    from intentions import project as project_intents, core_contract, validate_context
    authored_config_path=original/'config.json'
    authored_configuration=json.loads(authored_config_path.read_text()) if authored_config_path.exists() else {}
    authored_context=authored_configuration.get('authored_test_context',{})
    validate_context(authored_context)
    intention_contract=core_contract(library) if authored_context.get('intent_declarations') else None
    from .classifications import project_user, known_classes
    canonical_classes=known_classes(library)
    evidence=rows(capture/'evidence.jsonl'); telemetry=rows(original/'trace.jsonl');frames=rows(capture/'native/frames.jsonl')
    tmap,fmap=verify_join(evidence,telemetry,frames,diagnostic_fixture=diagnostic_fixture)
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
    from .inventory_observations import observations as inventory_observations, project as project_inventory, SUPPORTED_ATOMS as INVENTORY_ATOMS, complete_generated_lanes,retained_static_inventory,project_static_inventory
    inventory_records = inventory_observations(original, telemetry, native_facts,
                                               set(source_manifest.get('required_observations', []))|set(INVENTORY_ATOMS))
    inventory_projection = {atom: [] for atom in inventory_records}
    from .inventory_observations import Evidence
    original_source=Evidence(original.parent)
    static_inventory=retained_static_inventory(original_source)
    configuration=json.loads((original/'config.json').read_text()) if (original/'config.json').exists() else {}
    from context_catalogue import public_road_ids
    road_declaration=(static_inventory or {}).get('authored_road_access')
    public_way_roads=public_road_ids(original/'road.xodr',configuration,road_declaration,sha(original/'road.xodr'))
    if public_way_roads and road_declaration is None:
        values=dict(configuration.get('authored_test_context',{}).get('core_assumptions',[]))
        if values.get('asm.public_highway') is not True:raise ValueError('Public-way regions need an explicit administrative assumption')
        if any(e.get('original_observations',{}).get('map_context',{}).get('declared_public_way_road_ids')!=public_way_roads for e in evidence):
            raise ValueError('Public-way role declaration differs from original graph observations')
    map_sources={};map_region_sources={}
    from pipeline_paths import OUTPUT_ROOT
    regions,polygons,lane_ids=static_map(original/'road.xodr',junctions=True,junction_report=junction_report,
                                      native_junction_boxes=native_facts.get('junctions',[]),
                                      include_non_driving=True,public_way_roads=public_way_roads,source_roads=map_sources,
                                      source_regions=map_region_sources,
                                      cache=OUTPUT_ROOT/'state/cache/maps',
                                      complete_map=complete_generated_lanes(source_manifest,native_facts,sha(original/'road.xodr')))
    from .roadways import merge_highways
    merged,map_issues=merge_highways(original/'road.xodr',regions,polygons,map_sources,(road_declaration or {}).get('way_groups',[]))
    if map_issues:junction_report.extend({'unknown_geometry':issue} for issue in map_issues)
    highways={}
    for region in regions:
        if region['kind']=='highway':
            for road in map_sources.get(region['id'],[]):highways.setdefault(road,[]).append(region['id'])
    for region in regions:
        roads=map_sources.get(region['id'],[])
        if region['kind']!='highway' and roads and all(road in highways for road in roads):
            region['ways']=sorted({ident for road in roads for ident in highways[road]})
    if merged:
        from .compatibility import remap_regions
        numbering={r['id']:i for i,r in enumerate(regions,1) if r['id']!=i}
        # Re-key directly to avoid interpreting a compacted ID as another old ID.
        old_ids={r['id']:(r['id'] if r['id']>=10**12 else i) for i,r in enumerate(regions,1)}
        for region in regions:
            region['id']=old_ids[region['id']]
            if 'ways' in region:region['ways']=[old_ids[v] for v in region['ways']]
            lane=region.get('lane',{})
            for key in ('left','right','enters_intersection'):
                if key in lane:lane[key]=old_ids[lane[key]]
            if 'leads_to' in lane:lane['leads_to']=[old_ids[v] for v in lane['leads_to']]
        polygons={old_ids[k]:v for k,v in polygons.items()}
        lane_ids={k:old_ids[v] for k,v in lane_ids.items()}
        map_sources={old_ids[k]:v for k,v in map_sources.items() if k in old_ids}
        map_region_sources={old_ids[k]:v for k,v in map_region_sources.items() if k in old_ids}
    from .native_control_observations import read_observations as native_control_observations
    inventory_records.update(native_control_observations(original,telemetry,lane_ids,regions,
        source_manifest.get('required_observations', [])))
    inventory_projection = {atom: [] for atom in inventory_records}
    from .native_road_profile import apply as apply_native_road_profile
    native_road_profile = apply_native_road_profile(original,telemetry,regions,polygons)
    painted=painted_map_objects(original/'road.xodr')
    for observation in painted:
        region=observation['region'];region['id']=len(regions)+1
        regions.append(region)
        if 'boundary' in region:polygons[region['id']]=observation['shape']
    centre_lines=native_centre_lines(original/'road.xodr')
    for observation in centre_lines:
        region=observation['region'];region['id']=len(regions)+1
        regions.append(region);polygons[region['id']]=observation['shape']
    entrance_projection=None
    if source_manifest.get('observation_contract_version',0)>=3:
        from .entrance_associations import project as project_entrances
        entrance_projection=project_entrances(regions,polygons,lane_ids,painted,evidence)
    from .entrance_associations import resolve_case_references
    entrance_refs=resolve_case_references(authored_configuration,painted,len(evidence),
        'st.entrance_of' in source_manifest.get('required_observations',[]))
    # Recorded creation events establish ego class independently of cell/law text.
    recorder=(capture/'recorder_info.txt').read_text()
    blueprint=re.search(r'Create '+str(evidence[0]['actor_id'])+r': ([^ ]+)',recorder)
    if not blueprint:raise ValueError('Recorded subject blueprint unavailable')
    ego_classes,unknown_classes=classes(blueprint.group(1),library)
    if ego_classes is None:raise ValueError('Unclassifiable subject')
    original_packets=source_packets(original_source,(),read_graphs=False)
    times=[e['recording_time_s'] for e in evidence]
    yaw=rates(times,[e['ego']['heading_deg'] for e in evidence])
    motion_frames=[{'t':round(t*1000),'users':[]} for t in times]
    for index,event in enumerate(evidence):
        actors={a['actor_id']:a for a in event.get('original_observations',{}).get('participants',[])}
        actors.update(participant_records.get(event['original_frame'],{}))
        for aid,actor in actors.items():
            if 'heading_deg' in actor:
                angle=math.radians(-actor['heading_deg'])
                motion_frames[index]['users'].append({'track':aid,'kin':{'heading':[math.cos(angle),math.sin(angle)]}})
    marking_sets={}; obstacles=recorded_traffic_props(recorder); raw_keys=set(); raw_hashes={}; devices={}
    # Scan raw map/prop observations before emitting scenes: static objects repeat.
    for frame_index,e in enumerate(evidence):
        path=capture/'native'/fmap[e['replay_frame']]['base']
        if not path.is_file():raise ValueError('Raw graph missing: '+str(path))
        graph=load_graph(path);raw_hashes[e['replay_frame']]=sha(path)
        if graph.graph.get('frame')!=e['replay_frame']:raise ValueError('Raw graph frame mismatch')
        for node,a in graph.nodes(data=True):
            if acquisition=='original_live_run' and 'forward' in a and a.get('sem_class','').startswith(('vehicle.','walker.')):
                aid=a.get('carla_id',a.get('entity_id'))
                if aid is not None and not any(u['track']==aid for u in motion_frames[frame_index]['users']):
                    motion_frames[frame_index]['users'].append({'track':aid,'kin':{'heading':xy(a['forward'])}})
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
                    merge_device_governance(old,static)
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
    from .roadways import validate_map
    validate_map(regions)
    for ident,key in enumerate(sorted(devices),1):devices[key]['id']=ident
    output.mkdir(parents=True,exist_ok=False)
    if entrance_projection is not None:
        (output/'entrance_associations.json').write_text(json.dumps(entrance_projection,indent=2)+'\n')
    source_paths={'capture_evidence':capture/'evidence.jsonl','frame_index':capture/'native/frames.jsonl','original_telemetry':original/'trace.jsonl','map':original/'road.xodr','recorder_info':capture/'recorder_info.txt','capture_manifest':capture/'manifest.json'}
    if static_inventory:source_paths['static_map_inventory']=original/'static_map_inventory.json'
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
            'static_inventory_receipt':static_inventory,
            'full_core':str(full_core(library)), 'subject_blueprint':blueprint.group(1),
            'native_junction_mapping':junction_report,
            'authored_speed_control_portions':control_portions,
            'scenario_geometry_projection':scenario_geometry,
            'native_road_profile_projection':native_road_profile,
            'native_painted_objects':[dict(o['source'],region_id=o['region']['id']) for o in painted],
            'native_centre_lines':[dict(o['source'],region_id=o['region']['id'])for o in centre_lines],
            'adapter_sources':{p.name:sha(p) for p in (Path(__file__).parent/'adapter.py',Path(__file__).parent/'geometry.py',Path(__file__).parent/'visibility.py',Path(__file__).parent/'control_portions.py',Path(__file__).parent/'scenario_geometry.py',Path(__file__).parent/'inventory_observations.py',Path(__file__).parent/'entrance_associations.py')},
            'methods':{'position':'body centre from recorded bounding-box vertices; CARLA y reflected',
                       'speed':'original live telemetry; mph multiplied by 0.44704',
                       'participant_motion':'original same-frame actor.get_velocity and body telemetry, including measured actors outside the graph crop; no visibility inferred' if participant_records else ('original live graph actor.get_velocity only' if acquisition=='original_live_run' else 'replay motion omitted; unknown'),
                       'yaw_rate':'unwrapped reflected heading; central/one-sided finite difference; degrees/s; subject-only estimate',
                       'path_length':'trapezoidal integration of original speed; gaps leave unknown',
                       'occupancy':'recorded convex body footprint intersects 2 m sampled OpenDRIVE lane/roadway polygons',
                       'sight_distance':'subject-relative minimum sampled clear-side bound over inventoried incoming lanes; declared virtual eye height to nine actual body samples; censored bounds and rays retained',
                       'weather':'darkness: sun altitude < 0; precipitation/wetness: parameter > 0; classifications are estimates'},
            'limitations':['Sight distance is a time-varying simulation proxy with declared eye-height/body samples and sampling uncertainty; it is not an exact physical cutoff, driver recognizability or st.sight_along_way. rel.visible requires separate original subject-to-user body rays.',
                           'Observed native light states include off; missing lamps are never inferred from controller signals.',
                           'Normalized steering control is not wheel angle; commanded gear is not observed gear.',
                           'Omitted device.governs is unknown; an observed empty list governs nothing.',
                           'Curved lanes have no single direction vector; lane direction omitted there.',
                           'Recorder-only traffic props establish existence/position but not a boundary; incomplete geometry leaves occupancy unknown because Core has no per-region observation mask.',
                           'Only captured/map-supported entities are emitted. Complete source-bound static inventories or original same-frame inventories establish absence. Without either, a native empty list alone does not exclude additional rendered or unmarked regions.',
                           'OpenDRIVE line/arc geometry only; unsupported geometry fails conversion.',
                           'Compatible native road segments share roadway regions. Variable surveyed grades remain source samples, not overlapping roadway patches.'],
            'structures_without_observed_boundary':[r['id'] for r in regions if 'boundary' not in r],
            'occupancy_complete':len(polygons)==len(regions),
            'raw_attribute_keys':sorted(raw_keys),'supplementary_evidence':'supplementary_evidence.jsonl',
            'production_contract':source_manifest.get('observation_contract_version'),
            'visibility_frames_with_scalar':0, 'visibility_frames_without_scalar':0,
            'visibility_missing_reasons':{}, 'decoder_validation':'not_run'}
    period=sorted(times[i]-times[i-1] for i in range(1,len(times)))[(len(times)-1)//2] if len(times)>1 else 0
    travelled=0.;gapped=False
    from authored_context import assumptions
    authored_assumptions=assumptions(authored_context)
    if intention_contract:report['intention_contract']=intention_contract
    from .geometry import lane_segments,compile_lane_segments,project_lane_segments,entrance_geometry_fields
    partition={};partition_shapes=None
    if 'st.lane_direction' in source_manifest.get('required_observations',[]):
        source_fields={r['id']:{'lane':r.get('lane',{}),'_lane_source':map_region_sources[r['id']]}
            for r in regions if 'samples' in map_region_sources.get(r['id'],{})}
        source_fields.update(entrance_geometry_fields(original/'road.xodr',regions))
        partition,partition_issues=lane_segments({'structures':regions},source_fields)
        partition_shapes=compile_lane_segments(partition,source_fields) if partition else None
        report['lane_partition']={'lanes':len(partition),'pieces':sum(len(p)for p in partition.values()),'issues':partition_issues}
    report['methods']['lane_direction']='Native constant heading, or local sampled chord estimates on law-required curved lane partitions'
    report['limitations']=[('Curved lane direction is a local sampled chord estimate; lanes outside the requested direction scope retain unknown direction.'
        if note=='Curved lanes have no single direction vector; lane direction omitted there.' else note) for note in report['limitations']]
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
                    value=observed_inoperative(device.get('indications'))
                    if value is not None:current_devices[key]['inoperative']=value
                if node=='ego':
                    observed_signals=signals(a) if acquisition=='original_live_run' else {}
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
                observed_signals=signals(a) if acquisition=='original_live_run' else {}
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
            for user in users:
                if 'yaw_rate' not in user['kin']:
                    value=heading_rate(motion_frames[i-1] if i else None,motion_frames[i],
                        motion_frames[i+1] if i+1<len(motion_frames) else None,user['track'],period*1000)
                    if value is not None:user['kin']['yaw_rate']=value
            packet=original_packets.get(round(e['recording_time_s']*1000),{})
            for user in users:
                measured_lamps=packet.get('ego_lamps',{}) if user['track']==e['actor_id'] else packet.get('actors',{}).get(user['track'],{})
                if measured_lamps:user.setdefault('sig',{}).update(measured_lamps)
            weather=e['world'].get('weather',{});env={}
            for key,target,test in [('sun_altitude_angle','darkness',lambda v:v<0),('precipitation','precipitation',lambda v:v>0),('wetness','wet_road',lambda v:v>0)]:
                if key in weather:env[target]=test(weather[key])
            measured_environment, environmental_mapping=project_environment(environment_packet,row,e['original_frame'])
            env.update(measured_environment)
            structures, visibility_mapping = attach_visibility(regions, polygons, footprint, e.get('visibility'), lane_ids)
            if entrance_projection is not None:
                for structure in structures:
                    association=entrance_projection['frames'][i]['associations'].get(structure['id'])
                    if association is not None:
                        structure['entrance_of']=association
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
            if authored_context.get('intent_declarations'):
                scene['intents']=project_intents(authored_context,scene,original_frame=e['original_frame'],time_s=e['recording_time_s'])
            scene['users']=[project_user(user,canonical_classes) for user in scene['users']]
            if not public_way_roads:preserve_inventory_unknown(scene,['highway'])
            inventory_frame = project_inventory(scene, inventory_records, i)
            if static_inventory:
                project_static_inventory(scene,static_inventory)
                if 'crosswalk' in static_inventory['kinds']:
                    count=static_inventory['kinds']['crosswalk']['count']
                    inventory_frame['st.crosswalk']={'status':'observed_present' if count else 'verified_absent',
                        'frame':e['original_frame'],'scope':'entire_recorded_map','inventory_complete':True,
                        'method':'source-bound static inventory','map_sha256':static_inventory['map_sha256']}
            for atom, record in inventory_frame.items():inventory_projection[atom].append(record)
            if partition:project_lane_segments(scene,partition,partition_shapes,footprints)
            validate_scene(scene, library)
            if i:out.write(',')
            json.dump(serialized_scene(scene,bool(source_manifest.get('observation_contract_version'))),out,separators=(',',':'),allow_nan=False)
            # Full records, no field filtering. Raw graph remains immutable and
            # hash-addressed; no source concept is silently lost by the adapter.
            extra.write(json.dumps({'evidence':e,'original_telemetry':row,'original_participants':participant_records.get(e['original_frame'],{}),'raw_graph':{'path':str(graph_path),'sha256':raw_hashes[e['replay_frame']]},'world_scene_t':scene['t'],'visibility_mapping':visibility_mapping,'environmental_mapping':environmental_mapping},separators=(',',':'),allow_nan=False)+'\n')
        out.write(']}\n')
    required = set(source_manifest.get('required_observations', []))
    capability = manifest(library)
    report['capability_absence_reasons']={atom:('derived by Core from concrete kinds; not independently acquired'
        if atom=='st.travel_region' else 'no validated source-wide acquisition path')
        for atom,value in capability['atoms'].items() if value=='absent'}
    if entrance_projection is not None:
        report['entrance_associations']={'path':str(output/'entrance_associations.json'),
            'sha256':sha(output/'entrance_associations.json'),
            'states':len(entrance_projection['states']),
            'observed_regions':len(painted),
            'method':entrance_projection['method']}
    if source_manifest.get('observation_contract_version'):
        from .atom_contract import inventory, required_coverage
        contract=inventory(library,capability['atoms'])
        # Conversion already retains all original frames. A separate atom audit
        # validates required values, not only presence in a capability manifest.
        scenes=json.loads((output/'trace.json').read_text())['scenes']
        coverage=required_coverage(required,capability,scenes,inventory_projection,entrance_refs)
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
    if intention_contract and core_contract(library)!=intention_contract:
        raise ValueError('Authoritative intention Core sources changed during conversion')
    report['required_observations'] = sorted(required)
    from shared_manifest import link as link_manifest
    from pipeline_paths import OUTPUT_ROOT
    link_manifest(OUTPUT_ROOT, output, capability)
    for name,data in [('adapter_report.json',report)]:
        (output/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    return report


LAMP_BITS = {'light_Position': 1, 'light_LowBeam': 2, 'light_HighBeam': 4,
             'light_Brake': 8, 'light_RightBlinker': 16, 'light_LeftBlinker': 32,
             'light_Reverse': 64}

def lamp_state(bits):
    if type(bits) is not int or bits < 0:
        raise ValueError('Native light mask must be an observed nonnegative integer')
    return signals({key: bool(bits & bit) for key, bit in LAMP_BITS.items()})


def milliseconds(row):
    value = row.get('time_s', row.get('recording_time_s'))
    return round(value * 1000) if isinstance(value, (int, float)) else None

def index_motion(packet,actor,source):
    """Keep same-frame native 3D motion for audit, never infer from controls."""
    aid=actor.get('actor_id');v=actor.get('velocity_mps');speed=actor.get('speed_mps')
    if type(aid) is not int or not isinstance(v,list) or len(v)!=3:return
    if not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in v):return
    if aid in packet.get('motion_conflicts',[]):return
    old=packet.setdefault('native_motion',{}).get(aid)
    if old and any(abs(a-b)>1e-5 for a,b in zip(old['velocity'],v)):
        packet['native_motion'].pop(aid,None);packet.setdefault('motion_conflicts',[]).append(aid);return
    packet['native_motion'][aid]={'velocity':v,'speed':speed,'source':source}


def audit_motion(scene,packet):
    """Classify planar/3D differences; fix only a proven scalar projection error."""
    from collections import Counter
    diagnostics=Counter();changes=Counter()
    for u in scene.get('users',[]):
        k=u.get('kin',{});v=k.get('velocity');speed=k.get('speed')
        if not isinstance(v,list) or speed is None:continue
        diagnostics['user_scenes_with_speed_and_velocity']+=1
        planar=math.sqrt(sum(x*x for x in v))
        if abs(planar-speed)<=1e-3:continue
        diagnostics['speed_planar_norm_differences']+=1
        native=packet.get('native_motion',{}).get(u['track'])
        if not native:
            diagnostics['speed_difference_without_bound_3d_sample']+=1;continue
        xyz=native['velocity'];native_speed=native.get('speed')
        if len(v)!=2 or any(abs(a-b)>1e-5 for a,b in zip(v,[xyz[0],-xyz[1]])):
            diagnostics['velocity_source_or_frame_disagreement']+=1;continue
        magnitude=math.sqrt(sum(x*x for x in xyz))
        if abs(speed-magnitude)<=1e-5:
            diagnostics['speed_difference_explained_by_vertical_velocity']+=1
        elif isinstance(native_speed,(int,float)) and math.isfinite(native_speed) and abs(native_speed-magnitude)<=1e-5:
            k['speed']=native_speed;changes['recovered_same_frame_speed']+=1
        else:diagnostics['native_motion_samples_inconsistent']+=1
    return changes,diagnostics


def source_packets(evidence, required=(), *, read_graphs=True):
    """Index native light and signal measurements by exact retained timestamp."""
    packets = {}
    def at(row):
        stamp = milliseconds(row)
        return packets.setdefault(stamp, {'actors': {}, 'signals': {}}) if stamp is not None else None
    def same_frame(row, packet):
        frame, stamp = packet.get('native_frame'), packet.get('native_time')
        return (frame is not None and row.get('frame', frame) == frame
                and isinstance(stamp, (int, float))
                and isinstance(row.get('time_s'), (int, float))
                and abs(row['time_s']-stamp) <= 1e-6)
    for row in evidence.rows('trace.jsonl'):
        packet = at(row)
        if packet is not None:
            packet['native_frame']=row.get('frame');packet['native_time']=row.get('time_s')
            if isinstance(row.get('velocity_mps'),list):
                packet['subject_motion']={k:row[k] for k in ('frame','time_s','velocity_mps','speed_mps') if k in row}
            for field in ('ego_lamp_bits', 'vehicle_light_state_bits'):
                if type(row.get(field)) is int:
                    packet['ego_lamps'] = lamp_state(row[field])
            measured = row.get('original_observations', {})
            for actor in measured.get('participants', []):
                index_motion(packet,actor,'trace.jsonl:original_observations')
                attrs = actor.get('light_attributes', {})
                if attrs:
                    packet['actors'][actor['actor_id']] = signals(attrs)
    for row in evidence.rows('weather_and_participants.jsonl'):
        packet = at(row)
        value = row.get('value', {})
        if packet is None:
            continue
        if type(value.get('ego_lamp_bits')) is int:
            packet['ego_lamps'] = lamp_state(value['ego_lamp_bits'])
        for actor in value.get('participants', []):
            if same_frame(row, packet):
                index_motion(packet,actor,'weather_and_participants.jsonl')
            aid = actor.get('actor_id', actor.get('id'))
            if aid is None:
                continue
            attrs = actor.get('light_attributes')
            if attrs:
                packet['actors'][aid] = signals(attrs)
        for head in value.get('signal_indications', []):
            if head.get('state_availability') == 'queried':
                position = head.get('position_m')
                if position and len(position) >= 2:
                    key = (round(position[0], 3), round(-position[1], 3))
                    old = packet['signals'].get(key)
                    packet['signals'][key] = head['state'] if old in (None, head['state']) else 'ambiguous'
    for row in evidence.rows('ego_turn_indicator.jsonl'):
        value = row.get('value', {})
        packet = at(row)
        # reported_mask is measured device state; command is never used.
        if packet is not None and type(value.get('reported_mask')) is int and 'reported_device_state' in value:
            packet['ego_lamps'] = lamp_state(value['reported_mask'])
    # These are original measured channels, not labels or scenario requests.
    # Read only explicit native lamp masks, actor light attributes and queried
    # signal states; unavailable markers and frozen/controller flags supply none.
    sidecars=('signal_indications.jsonl','vehicle_turn_signal_history.jsonl',
        'governing_signal_indication.jsonl','signal_and_scene_state_history.jsonl',
        'traffic_signal_operational_state.jsonl','traffic_signal_state_history.jsonl',
        'native-motion.jsonl','synchronized_motion_history.jsonl',
        'synchronized_motion_histories.jsonl','synchronized_motion_records.jsonl',
        'identity_preserving_motion_records.jsonl','ego_motion_record.jsonl')
    for name in sidecars:
        for row in evidence.rows(name):
            packet=at(row)
            if packet is None:continue
            value=row.get('value',row.get('states',{}))
            if not isinstance(value,dict):continue
            indicator=value.get('ego_indicator',{})
            if indicator.get('method')=='Vehicle.get_light_state' and type(indicator.get('raw_light_state_bits')) is int:
                packet.setdefault('lamp_sources',[]).append({'subject':True,'lamps':lamp_state(indicator['raw_light_state_bits'])})
            candidates=[value]+[v for v in value.values() if isinstance(v,dict)]
            for key in ('devices','governing_devices','participants'):
                candidates.extend(value.get(key,[]) if isinstance(value.get(key),list) else [])
            for actor in candidates:
                aid=actor.get('actor_id')
                if type(aid) is not int:continue
                if same_frame(row, packet):
                    index_motion(packet,actor,name)
                lamps=signals(actor.get('light_attributes',{}))
                if type(actor.get('lamp_bits')) is int:lamps.update(lamp_state(actor['lamp_bits']))
                if lamps:packet.setdefault('lamp_sources',[]).append({'track':aid,'lamps':lamps})
                state=actor.get('state')
                if state in ('Red','Yellow','Green','Off','Unknown'):
                    known=packet.setdefault('actor_signals',{}).get(aid)
                    packet['actor_signals'][aid]=state if known in (None,state) else 'ambiguous'
                position=actor.get('position_m',actor.get('transform',{}).get('position_m'))
                if isinstance(position,dict):
                    position=[position['x'],position['y']] if {'x','y'}<=set(position) else None
                if isinstance(position,(list,tuple)) and len(position)>=2 and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in position[:2]):
                    packet.setdefault('device_positions',{})[aid]=(round(position[0],3),round(-position[1],3))
    for packet in packets.values():
        for aid,state in packet.get('actor_signals',{}).items():
            position=packet.get('device_positions',{}).get(aid)
            if position is not None:
                old=packet['signals'].get(position)
                packet['signals'][position]=state if old in (None,state) else 'ambiguous'
    for event in evidence.rows('capture/evidence.jsonl'):
        motion_packet=at(event)
        if motion_packet is not None and motion_packet.get('native_frame')==event.get('original_frame'):
            row=motion_packet.get('subject_motion',{})
            if abs(row.get('time_s',-1)-event['recording_time_s'])<=1e-6:
                index_motion(motion_packet,dict(row,actor_id=event['actor_id']),'trace.jsonl:original_frame')
        if event.get('visibility') is not None:
            packet = at(event)
            if packet is None or not same_frame({'frame':event.get('original_frame'),
                    'time_s':event.get('recording_time_s')}, packet):
                raise ValueError('Visibility frame/time differs from original telemetry')
            vertices = event.get('ego', {}).get('body_vertices_m')
            if vertices:
                packet['subject_visibility'] = {'subject':event['actor_id'],
                    'body_vertices_m':vertices, 'visibility':event['visibility']}
        measured=event.get('original_observations',{})
        if not measured.get('participants') and not measured.get('devices'):continue
        if measured.get('frame')!=event.get('original_frame'):
            raise ValueError('Original observation frame mismatch')
        if abs(measured.get('time_s',event['recording_time_s'])-event['recording_time_s'])>1e-6:
            raise ValueError('Original observation timestamp mismatch')
        packet=at(event)
        if packet is None:continue
        for actor in measured.get('participants',[]):
            index_motion(packet,actor,'capture/evidence.jsonl:original_observations')
            aid=actor.get('actor_id')
            lamps=signals(actor.get('light_attributes',{}))
            if aid==event.get('actor_id'):
                if lamps:packet.setdefault('ego_lamps',{}).update(lamps)
            elif aid is not None and lamps:packet['actors'].setdefault(aid,{}).update(lamps)
        for device in measured.get('devices',[]):
            if not device.get('blueprint','').startswith('traffic.traffic_light'):continue
            position=device.get('position_m');state=device.get('state')
            if position and state in ('Red','Yellow','Green','Off','Unknown'):
                key=(round(position[0],3),round(-position[1],3))
                old=packet['signals'].get(key)
                packet['signals'][key]=state if old in (None,state) else 'ambiguous'
    if read_graphs:
        times,read=original_graph_reader(evidence)
        for stamp in times:
            measured=read(stamp)
            packet=packets.setdefault(stamp,{'actors':{},'signals':{}})
            for key,value in measured.items():
                if isinstance(value,dict):packet.setdefault(key,{}).update(value)
                else:packet[key]=value

    return packets

def yaw_estimates(trace):
    """Differentiate measured trace headings, without inventing samples or identities."""
    from trace_json import scenes
    import collections
    tracks = collections.defaultdict(list)
    for index, (scene, _) in enumerate(scenes(trace)):
        for user in scene.get('users', []):
            h = user.get('kin', {}).get('heading')
            if h is not None and len(h) == 2 and all(math.isfinite(v) for v in h):
                tracks[user['track']].append((index, scene['t'], math.atan2(h[1], h[0])))
    result = collections.defaultdict(dict)
    for track, observations in tracks.items():
        if len(observations) < 2:
            continue
        intervals = [b[1]-a[1] for a,b in zip(observations,observations[1:]) if b[0] == a[0]+1 and b[1] > a[1]]
        if not intervals:
            continue
        period = sorted(intervals)[len(intervals)//2]
        for i, value in enumerate(observations):
            a = observations[max(0,i-1)]
            b = observations[min(len(observations)-1,i+1)]
            if b[1] <= a[1] or b[0]-a[0] != min(len(observations)-1,i+1)-max(0,i-1):
                continue
            window = observations[max(0,i-1):min(len(observations),i+2)]
            if any(y[1]-x[1] > 1.5*period for x,y in zip(window,window[1:])):
                continue
            change = sum((y[2]-x[2]+math.pi)%(2*math.pi)-math.pi for x,y in zip(window,window[1:]))
            if any(abs((y[2]-x[2]+math.pi)%(2*math.pi)-math.pi) > math.pi/2 for x,y in zip(window,window[1:])):
                continue
            result[value[0]][track] = math.degrees(change) / ((b[1]-a[1])/1000)
    return result

def repair_scene(scene, required, packet, fields, yaw, native_lanes=None):
    import collections
    changes = collections.Counter()
    # Remove unbound values before reprojecting this frame from retained rays.
    old_sight={r['id']:r['sight_distance'] for r in scene.get('structures',[]) if 'sight_distance' in r}
    for region in scene.get('structures', []):
        region.pop('sight_distance', None)
    measured_sight = packet.get('subject_visibility')
    if measured_sight and measured_sight['subject'] == scene.get('subject'):
        from shapely.geometry import Polygon
        _, _, footprint = body(measured_sight['body_vertices_m'], 0)
        polygons = {r['id']: Polygon(r['boundary']) for r in scene.get('structures', [])
                    if r.get('kind') in ('lane','roadway') and r.get('boundary')}
        scene['structures'], mapping = attach_visibility(scene.get('structures', []), polygons,
                                                         footprint, measured_sight['visibility'], native_lanes or {})
    new_sight={r['id']:r['sight_distance'] for r in scene.get('structures',[]) if 'sight_distance' in r}
    removed=len(set(old_sight)-set(new_sight))
    projected=sum(old_sight.get(k)!=v for k,v in new_sight.items())
    if removed:changes['removed_unbound_sight_distance'] += removed
    if projected:changes['projected_measured_sight_distance'] += projected

    native_lanes=native_lanes or {}
    for user in scene.get('users', []):
        sig = user.get('sig', {})
        if 'hand_signal' in sig:
            del sig['hand_signal']; changes['A11_removed_unsupported_field'] += 1
        for key in ('left_indicator_enabled', 'right_indicator_enabled'):
            if key in sig:
                del sig[key]; changes['A1_removed_ignored_key'] += 1
        sources=[packet.get('actors',{}).get(user['track'],{})]
        if user['track']==scene.get('subject'):sources.append(packet.get('ego_lamps',{}))
        sources.extend(item['lamps'] for item in packet.get('lamp_sources',[]) if item.get('track')==user['track'] or (item.get('subject') and user['track']==scene.get('subject')))
        measured={}
        for key in {k for source in sources for k in source}:
            values=[source[key] for source in sources if key in source]
            if all(v==values[0] for v in values):measured[key]=values[0]
            elif key in sig:
                del sig[key];changes['conflicting_lamp_measurement_made_unknown']+=1
        if 'sig.turn_indicator' in required and 'hazard' in measured:
            if sig.get('hazard') != measured['hazard']:
                sig['hazard']=measured['hazard'];changes['measured_hazard']+=1
            if measured['hazard'] and 'turn_indicator' in sig:
                del sig['turn_indicator'];changes['hazard_turn_side_made_unknown']+=1
        for key, value in measured.items():
            if ('sig.' + key) in required and sig.get(key) != value:
                sig[key] = value; changes['measured_'+key] += 1
        if sig or 'sig' in user:
            user['sig'] = sig
        if 'kin.yaw_rate' in required and 'yaw_rate' not in user.get('kin', {}) and user['track'] in yaw:
            user.setdefault('kin', {})['yaw_rate'] = yaw[user['track']]
            changes['A12_yaw_rate'] += 1
    lane_atoms = {'direction':'st.lane_direction', 'width':'st.lane_width',
                  'marking_left':'st.lane_marking', 'marking_right':'st.lane_marking',
                  'enters_intersection':'st.lane_enters', 'leads_to':'st.lane_connectivity',
                  'left':'st.lane_adjacency','right':'st.lane_adjacency',
                  'ordinal':'st.lane_adjacency','count':'st.lane_adjacency'}
    markings={}
    for (native,side),value in packet.get('lane_markings',{}).items():
        if native in native_lanes:markings[(native_lanes[native],side)]=value
    for region in scene.get('structures', []):
        association=packet.get('entrances',{}).get(region['id'])
        if 'st.entrance_of' in required and association is not None and 'entrance_of' not in region:
            region['entrance_of']=association;changes['A7_entrance']+=1
        for side in ('left','right'):
            key='marking_'+side
            if 'st.lane_marking' in required and (region['id'],side)in markings and key not in region.get('lane',{}):
                region.setdefault('lane',{})[key]=markings[(region['id'],side)];changes['map_'+key]+=1
        for key, value in fields.get(region['id'], {}).items():
            if lane_atoms.get(key) in required and region.setdefault('lane', {}).get(key)!=value:
                region['lane'][key] = value; changes['map_'+key] += 1
    from traffic_spec_adapter.compatibility import GOVERNABLE
    region_kinds={r['id']:r['kind']for r in scene.get('structures',[])}
    for device in scene.get('devices',[]):
        if any(region_kinds.get(r) not in GOVERNABLE for r in device.get('governs',[])):
            # Preserve the original edges in the archive; no supported replacement
            # carrier can be inferred from overlap alone.
            device.pop('governs',None);changes['invalid_governance_made_unknown']+=1
    indication = {'Red':'circular_red','Yellow':'circular_yellow','Green':'circular_green','Off':'dark'}
    positions=collections.Counter(tuple(round(v,3)for v in d['position'])for d in scene.get('devices',[])if d.get('position')is not None)
    for device in scene.get('devices', []):
        if 'unknown' in device.get('indications',[]):
            device.pop('indications',None);device.pop('inoperative',None)
            changes['unknown_indication_made_unknown']+=1
        position = device.get('position')
        key = tuple(round(v, 3) for v in position) if position and len(position) == 2 else None
        state = packet.get('signals', {}).get(key) if positions[key]==1 else None
        if state is None and positions[key]==1:
            actors=[aid for aid,pos in packet.get('device_positions',{}).items() if pos==key and aid in packet.get('actor_signals',{})]
            if len(actors)==1:state=packet['actor_signals'][actors[0]]
        if state in ('Unknown','ambiguous') and 'indications' in device:
            device.pop('indications',None);device.pop('inoperative',None)
            changes['unknown_indication_made_unknown']+=1
        controls=packet.get('governance',{}).get(key)
        if 'dev.governs' in required and positions[key]==1 and controls and all(k in native_lanes for k in controls) and 'governs' not in device:
            device['governs']=sorted({native_lanes[k]for k in controls});changes['A7_governance']+=1
        if 'dev.traffic_signal' in required and device.get('kind') == 'traffic_signal' and state in indication:
            value = [indication[state]]
            if device.get('indications') != value:
                device['indications'] = value; changes['A6_indication'] += 1
    changes.update(project_operability(scene.get('devices',[])))
    return changes

def preserve_inventory_unknown(scene, uncertain):
    changes=0
    parent={'one_way_roadway':'roadway'}
    for region in scene.get('structures',[]):
        unknown=set(region.get('unobserved_kinds',[]))
        for kind in uncertain:
            if region['kind']==kind:continue  # Keep an already observed object.
            if kind in parent and region['kind']!=parent[kind]:continue
            if kind not in unknown:unknown.add(kind);changes+=1
        if unknown:region['unobserved_kinds']=sorted(unknown)
    return changes



def heading_rate(previous, current, following, track, period):
    """Three-frame measured heading derivative; no interpolation over missing IDs."""
    window=[s for s in (previous,current,following) if s is not None]
    if len(window)<2:return None
    angles=[]
    for scene in window:
        candidates=[u for u in scene.get('users',[]) if u['track']==track]
        if len(candidates)!=1:return None
        h=candidates[0].get('kin',{}).get('heading')
        if not isinstance(h,list) or len(h)!=2 or not all(math.isfinite(v) for v in h) or not any(h):return None
        angles.append(math.atan2(h[1],h[0]))
    times=[s['t'] for s in window]
    if any(not 0<b-a<=1.5*period for a,b in zip(times,times[1:])):return None
    steps=[(b-a+math.pi)%(2*math.pi)-math.pi for a,b in zip(angles,angles[1:])]
    if any(abs(v)>math.pi/2 for v in steps):return None
    return math.degrees(sum(steps))/((times[-1]-times[0])/1000)


def reconstruct(trace, original, library, output, *, cache=None, required=(), read_graphs=False, context_recovery=None, inventory_recovery=None):
    """Repair retained trace data with the production projections; no legal monitor.

    Streams a three-scene window. Original evidence and frame identities stay
    immutable. Output is staged and must pass Core decoding before publication.
    """
    import collections
    import copy
    import time
    from trace_json import scenes
    from .inventory_observations import Evidence,retained_static_inventory,project_static_inventory
    from .geometry import retained_map, lane_segments, compile_lane_segments, project_lane_segments
    from .entrance_associations import retained_associations
    from .roadways import consolidate, apply_replacements, validate_map
    from .trace_contract import validate as validate_fields
    from .atom_contract import gaps
    from .classifications import known_classes,project_user
    trace,original,output=map(Path,(trace,original,output))
    started=time.monotonic();timings={}
    iterator=iter(scenes(trace));current,current_raw=next(iterator)
    following,following_raw=next(iterator,(None,None))
    first=copy.deepcopy(current)
    evidence=Evidence(original.parent)
    static_inventory=retained_static_inventory(evidence,inventory_recovery)
    canonical_classes=known_classes(library)
    frame_index=[(round(e['recording_time_s']*1000),e['actor_id']) for e in evidence.rows('capture/evidence.jsonl')]
    fields,lane_ids,additions,map_replacements,issues=retained_map(evidence,first,cache,static_inventory)
    identities={ident:value['_roadway_source'] for ident,value in fields.items() if '_roadway_source' in value}
    _,consolidation=consolidate(first,identities=identities)
    replacements=dict(consolidation['replacements']);replacements.update(map_replacements);issues.extend(consolidation['issues'])
    patched=apply_replacements(copy.deepcopy(first),replacements) if replacements else copy.deepcopy(first)
    patched['structures'].extend(copy.deepcopy(additions))
    for r in patched['structures']:
        patch=fields.get(r['id'],{})
        if patch.get('lane'):r.setdefault('lane',{}).update(patch['lane'])
    segments,segment_issues=lane_segments(patched,fields) if 'st.lane_direction' in required else ({},[])
    segment_shapes=compile_lane_segments(segments,fields) if segments else None
    issues.extend(segment_issues)
    entrance,entrance_issues=retained_associations(evidence,patched,lane_ids)
    issues.extend(entrance_issues)
    # Source packets may be expensive only when explicitly inspecting legacy raw
    # graphs. Direct measured sidecars are always checked, regardless of law.
    wanted=set(required)|{'sig.turn_indicator','sig.brake_lamp','sig.position_lamp',
        'sig.reverse_lamp','sig.hazard','sig.headlamp','kin.yaw_rate',
        'st.lane_direction','st.lane_marking','st.lane_width','st.lane_connectivity',
        'st.lane_enters','st.entrance_of','dev.traffic_signal','dev.governs'}
    packets=source_packets(evidence,wanted,read_graphs=False)
    graph_reader=None
    timings['evidence_and_map_seconds']=time.monotonic()-started
    from context_catalogue import RetainedContext
    context=RetainedContext(evidence,patched,context_recovery)
    diagnostics=collections.Counter()
    period=(following['t']-current['t']) if following else 0
    previous=None;count=0;changes=collections.Counter();missing=collections.Counter()
    output.parent.mkdir(parents=True,exist_ok=True)
    lane_fields={ident:value['lane'] for ident,value in fields.items() if value.get('lane')}
    static_entrance=entrance.get('static',{})
    changed_ways={ident:value for ident,value in fields.items() if 'boundary' in value and '_source_road_ids' in value}
    known_way_shapes={i:v['_way_geometry'] for i,v in changed_ways.items() if '_way_geometry' in v}
    from shapely import prepare
    prepare([v['_way_geometry']for v in fields.values()if '_way_geometry'in v])
    original_regions={r['id']:(r['kind'],r.get('boundary')) for r in first.get('structures',[])}
    length=0.;path_known=True
    write_started=time.monotonic()
    from contextlib import ExitStack
    with ExitStack() as stack:
        stream=None
        encoded_regions=None;last_regions=None
        while current is not None:
            if previous is not None and current['t']<=previous['t']:raise ValueError('Nonmonotone trace timestamps')
            if frame_index and (count>=len(frame_index) or frame_index[count]!=(current['t'],current['subject'])):
                raise ValueError('Retained original frame/subject join differs from trace')
            if any(original_regions.get(r['id'])!=(r['kind'],r.get('boundary')) for r in current.get('structures',[])):
                raise ValueError('Region geometry changed across frames; static native identity cannot be assumed')
            scene=apply_replacements(current,replacements,consolidation.get('property_merges',())) if replacements else current
            delta=collections.Counter()
            if replacements:delta['consolidated_roadways']+=len(replacements)
            scene['structures'].extend(copy.deepcopy(additions))
            if additions:delta['recovered_surface_regions']+=len(additions)
            for r in scene['structures']:
                if isinstance(r.get('curvature'),(int,float)) and r['curvature']<0:
                    r['curvature']=abs(r['curvature']);delta['curvature_magnitude']+=1
                value=fields.get(r['id'],{})
                if value.get('_unobserved_paint_boundary') and 'boundary' in r:
                    r.pop('boundary');scene['occupancy_observed']=[]
                    delta['removed_unmeasured_stop_line_boundary']+=1
                if 'boundary' in value and r.get('boundary')!=value['boundary']:
                    if value['boundary'] is None:r.pop('boundary',None)
                    else:r['boundary']=value['boundary']
                    delta['merged_highway_boundary']+=1
                if 'ways' in value and r.get('ways')!=value['ways']:
                    r['ways']=value['ways'];delta['native_way_membership']+=1
            packet=dict(packets.get(scene['t'],{}))
            packet['entrances']=dict(static_entrance,**{})|entrance.get(scene['t'],{})
            yaw={}
            for u in scene.get('users',[]):
                if 'yaw_rate' not in u.get('kin',{}):
                    rate=heading_rate(previous,current,following,u['track'],period)
                    if rate is not None:yaw[u['track']]=rate
            delta.update(repair_scene(scene,wanted,packet,lane_fields,yaw,lane_ids))
            if read_graphs:
                missing_lamps=any(u.get('classes') and 'motor_vehicle' in u['classes'] and
                    (any(k not in u.get('sig',{}) for k in ('brake_lamp','headlamp')) or
                     ('turn_indicator' not in u.get('sig',{}) and not u.get('sig',{}).get('hazard'))) for u in scene.get('users',[]))
                missing_heads=any(d['kind']=='traffic_signal' and not d.get('indications') for d in scene.get('devices',[]))
                missing_controls=any('governs' not in d for d in scene.get('devices',[])) and 'dev.governs' in required
                missing_marks=any(r['kind']=='lane' and any(k not in r.get('lane',{}) for k in ('marking_left','marking_right')) for r in scene['structures']) and 'st.lane_marking' in required
                if missing_lamps or missing_heads or missing_controls or missing_marks:
                    if graph_reader is None:_,graph_reader=original_graph_reader(evidence)
                    measured=graph_reader(scene['t'])
                    if measured:
                        measured['lamp_sources']=list(packet.get('lamp_sources',[]))+[{'track':track,'lamps':lamps} for track,lamps in packet.get('actors',{}).items()]+[{'subject':True,'lamps':packet.get('ego_lamps',{})}]
                        measured['actor_signals']=packet.get('actor_signals',{})
                        measured.setdefault('device_positions',{}).update(packet.get('device_positions',{}))
                        delta.update(repair_scene(scene,wanted,measured,lane_fields,{},lane_ids))

            # Existing measured values are retained; only absent subject path
            # length is filled, from contiguous original speed samples.
            subject=next((u for u in scene.get('users',[]) if u['track']==scene.get('subject')),None)
            speed=subject.get('kin',{}).get('speed') if subject else None
            if speed is None or not isinstance(speed,(int,float)) or not math.isfinite(speed):path_known=False
            if previous is not None:
                prior=next((u for u in previous.get('users',[]) if u['track']==scene.get('subject')),None)
                old=prior.get('kin',{}).get('speed') if prior else None
                dt=scene['t']-previous['t']
                if old is None or not 0<dt<=1.5*period:path_known=False
                if path_known:length+=(speed+old)/2*dt/1000
            if subject and path_known and 'path_length' not in subject.setdefault('kin',{}):
                subject['kin']['path_length']=length;delta['measured_subject_path_length']+=1
            motion_changes,motion_diagnostics=audit_motion(scene,packet)
            delta.update(motion_changes);diagnostics.update(motion_diagnostics)
            delta.update(context.project(scene))
            for index,user in enumerate(scene['users']):
                projected=project_user(user,canonical_classes)
                if projected!=user:
                    scene['users'][index]=projected
                    delta['canonical_user_classifications']+=1
            if static_inventory:
                classified=project_static_inventory(scene,static_inventory)
                if classified:delta['verified_static_kind_classifications']+=classified
            if segments:
                delta['segmented_lane_regions']+=project_lane_segments(scene,segments,segment_shapes)
            # Adding regions invalidates a blanket complete occupancy claim.
            # Compute new overlaps from measured body footprints where available.
            if additions:
                from shapely.geometry import Polygon
                if any('boundary' not in r and '_way_geometry' not in fields.get(r['id'],{}) for r in additions):scene['occupancy_observed']=[]
                for u in scene.get('users',[]):
                    k=u.get('kin',{});pos=k.get('position');h=k.get('heading');ext=k.get('extent')
                    if pos and h and ext:
                        norm=math.hypot(*h);fx,fy=h[0]/norm,h[1]/norm
                        footprint=Polygon([[pos[0]+a*ext[0]*fx-b*ext[1]*fy,pos[1]+a*ext[0]*fy+b*ext[1]*fx] for a,b in [(-1,-1),(1,-1),(1,1),(-1,1)]])
                        for region in additions:
                            if ((fields.get(region['id'],{}).get('_way_geometry') is not None and footprint.intersects(fields[region['id']]['_way_geometry'])) or ('boundary' in region and footprint.intersects(Polygon(region['boundary'])))):
                                scene.setdefault('occupies',[]).append([u['track'],region['id']])
                    else:scene['occupancy_observed']=[t for t in scene.get('occupancy_observed',[]) if t!=u['track']]
            if changed_ways:
                from shapely.geometry import Polygon
                known=known_way_shapes
                scene['occupies']=[pair for pair in scene.get('occupies',[]) if pair[1] not in known]
                if len(known)!=len(changed_ways):scene['occupancy_observed']=[]
                for user in scene.get('users',[]):
                    k=user.get('kin',{});pos=k.get('position');h=k.get('heading');ext=k.get('extent')
                    if pos is None or h is None or ext is None or math.hypot(*h)<=1e-9:
                        scene['occupancy_observed']=[t for t in scene.get('occupancy_observed',[])if t!=user['track']];continue
                    norm=math.hypot(*h);fx,fy=h[0]/norm,h[1]/norm
                    body=Polygon([[pos[0]+a*ext[0]*fx-b*ext[1]*fy,pos[1]+a*ext[0]*fy+b*ext[1]*fx]for a,b in [(-1,-1),(1,-1),(1,1),(-1,1)]])
                    scene['occupies'].extend([user['track'],ident]for ident,shape in known.items()if body.intersects(shape))
            # Complete Core decoding follows this stream. It checks every numeric
            # value, so repeating numeric traversal of static coordinates adds no gate.
            validate_scene(scene,library,check_numbers=False)
            if count==0:
                try:validate_map(scene['structures'])
                except ValueError as exc:
                    if 'Duplicate roadway geometry' not in str(exc):raise
                    issues.append('Saved coincident roadway footprints have different properties or unknown source identities; Core has no height/identity-uncertainty field. Preserved rather than merging from 2D overlap alone.')
            missing.update(gaps(scene,set(required)-{'sig.hand_signal'}))
            if delta and stream is None:
                stream=stack.enter_context(output.open('w'))
                stream.write('{"scenes":[')
                if count:
                    import itertools
                    for index,(_,prefix_raw) in enumerate(itertools.islice(scenes(trace),count)):
                        if index:stream.write(',')
                        stream.write(prefix_raw)
            if stream is not None:
                if count:stream.write(',')
                if delta:
                    # Map geometry dominates large traces and is usually static.
                    # Cache its encoding, but invalidate on any actual field change.
                    if last_regions!=scene['structures']:
                        last_regions=scene['structures']
                        encoded_regions=json.dumps(last_regions,separators=(',',':'),allow_nan=False)
                    dynamic={k:v for k,v in scene.items() if k!='structures'}
                    encoded=json.dumps(dynamic,separators=(',',':'),allow_nan=False)
                    stream.write(encoded[:-1]+',"structures":'+encoded_regions+'}')
                else:stream.write(current_raw)
            changes.update(delta);count+=1
            previous=current
            current,current_raw=following,following_raw
            following,following_raw=next(iterator,(None,None))
        if stream is not None:stream.write(']}\n')
    if frame_index and len(frame_index)!=count:raise ValueError('Retained original frame count differs from trace')
    timings['projection_and_write_seconds']=time.monotonic()-write_started
    return {'frames':count,'changes':dict(changes),'changed':bool(changes),
        'evidence_used':evidence.used,'evidence_issues':list(dict.fromkeys(evidence.problems)),
        'b_context':context.report(),'context_recovery_receipt':context_recovery,
        'static_inventory_receipt':static_inventory,'b_motion':dict(diagnostics),
        'b_roadways':{'removed_per_frame':len(replacements),'property_merges':len(consolidation.get('property_merges',[])),
                      'source_verified_regions':len(identities)},
        'handoff':list(dict.fromkeys(issues)), 'required_field_gaps':dict(missing),
        'required_atoms':sorted(required),'timings':timings,'carla_executions':0,'gpu_simulations':0}



def original_graph_reader(evidence):
    """Index once; decode an original graph only when a frame still needs data."""
    capture=evidence.path('capture/manifest.json')
    if capture is None or json.loads(capture.read_text()).get('acquisition')!='original_live_run':
        return {}, lambda stamp: {}
    frame_map={r['frame']:r for r in evidence.rows('capture/native/frames.jsonl')}
    events={milliseconds(e):e for e in evidence.rows('capture/evidence.jsonl')}
    def read(stamp):
        event=events.get(stamp)
        if event is None:return {}
        original=event.get('original_frame')
        if event.get('replay_frame')!=original or original not in frame_map:return {}
        path=evidence.path('capture/native/'+frame_map[original]['base'])
        if path is None:return {}
        graph=load_graph(path)
        if graph.graph.get('frame')!=original:raise ValueError('Native graph frame mismatch')
        packet={'actors':{},'signals':{}}
        packet.setdefault('lane_markings',{})
        packet.setdefault('governance',{})
        for node,attrs in graph.nodes(data=True):
            aid=attrs.get('carla_id',attrs.get('entity_id'))
            measured=signals(attrs)
            if node=='ego':packet.setdefault('ego_lamps',{}).update(measured)
            elif aid is not None and measured:packet['actors'].setdefault(aid,{}).update(measured)
            if attrs.get('sem_class')=='traffic.traffic_light':
                pos=attrs.get('vertex')
                if aid is not None and pos is not None:packet.setdefault('device_positions',{})[aid]=(round(float(pos[0]),3),round(-float(pos[1]),3))
                state=str(attrs.get('light_state','')).split('.')[-1]
                if pos is not None and len(pos)>=2:
                    key=(round(float(pos[0]),3),round(-float(pos[1]),3))
                    old=packet['signals'].get(key)
                    packet['signals'][key]=state if old in (None,state)else 'ambiguous'
            if attrs.get('sem_class','').startswith(('traffic.','landmark.')):
                pos=attrs.get('vertex')
                controls=[]
                for _,target,edge in graph.out_edges(node,data=True):
                    if edge.get('dist_relationship',edge.get('label'))!='controlsTrafficOf':continue
                    target_attrs=graph.nodes[target]
                    key=tuple(target_attrs.get(k)for k in ('waypoint_road_id','waypoint_section_id','waypoint_lane_id'))
                    if all(v is not None for v in key):controls.append(key)
                observed=attrs.get('observed_governs')
                if isinstance(observed,list):controls=[tuple(k)for k in observed]
                if isinstance(observed,list) and controls and pos is not None:
                    packet['governance'][(round(float(pos[0]),3),round(-float(pos[1]),3))]=controls
            if 'waypoint_lane_id' in attrs:
                key=tuple(attrs.get(k)for k in ('waypoint_road_id','waypoint_section_id','waypoint_lane_id'))
                for side in ('left','right'):
                    typ=attrs.get(side+'_lane_marking_type');color=attrs.get(side+'_lane_marking_color')
                    mapping={'Broken':'broken','Solid':'solid','SolidSolid':'double_solid','BottsDots':'dotted','Curb':'curb','NONE':'none','None':'none'}
                    if typ in mapping and color in ('White','Yellow'):
                        packet['lane_markings'][(key,side)]=[mapping[typ],color.lower()]
        return packet
    return events,read
