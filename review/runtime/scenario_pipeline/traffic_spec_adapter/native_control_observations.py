"""Original native-control inventories and incoming-lane topology receipts.

This contract is limited to generated OpenDRIVE worlds using native CARLA
control mechanisms. It does not classify arbitrary custom rendered props as
controls or establish official authority. Older captures remain unsupported;
absence is never inferred from an empty Core list or a configuration flag.
"""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ATOMS = {'dev.traffic_signal', 'st.lane_enters'}



def complete_lane_assignment(actor):
    """Resolve the documented CARLA TrafficLight lane-specific source contract.

    The original producer records the unfiltered get_affected_lane_waypoints
    response. A successful nonempty TrafficLight response is its complete lane
    assignment; no negative statement about junction authority is required.
    Group membership, stop waypoints and other device roles do not establish
    that contract. An empty response also occurs for an unmatched OpenDRIVE
    signal ID (CARLA 0.9.15 TrafficLight.cpp), so it is not verified absence.
    Known partial observations remain in original evidence when scope is unknown.
    """
    lanes = actor.get('affected_lanes')
    if lanes is None:
        return None
    if not isinstance(lanes, list) or any(
            not isinstance(lane, (list, tuple)) or len(lane) != 3
            or any(type(value) is not int for value in lane) for lane in lanes):
        raise ValueError('Malformed original device affected-lane observation')
    if 'affected_lanes' in actor.get('observation_errors', {}):
        raise ValueError('Conflicting original device affected-lane observation')
    if actor.get('blueprint') != 'traffic.traffic_light' or not lanes:
        return None
    return [tuple(lane) for lane in lanes]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_observations(original, telemetry, lane_ids, regions, required):
    original = Path(original)
    selected = set(required) & ATOMS
    stream = original/'native_control_inventory.jsonl'
    topology = original/'native_incoming_lane_topology.json'
    if not selected or not stream.exists() or not topology.exists():
        return {}  # No retrospective completeness claim for old captures.
    result = json.loads((original/'result.json').read_text())
    binding = result.get('completion', {}).get('binding')
    if not binding:
        raise ValueError('Native inventory requires a closed original attempt')
    from .inventory_observations import Evidence
    retained=Evidence(original.parent)
    for name in ('native_control_inventory.jsonl','native_incoming_lane_topology.json','construction.json','runner.py','road.xodr','trace.jsonl'):
        if retained.path(name) is None:raise ValueError('Unbound native control evidence: '+name)
    construction = json.loads((original/'construction.json').read_text())
    implementation = next(f['content'] for f in construction['files'] if f['path']=='runner.py')
    implementation_sha = hashlib.sha256(implementation.encode()).hexdigest()
    if sha(original/'runner.py') != implementation_sha:
        raise ValueError('Native inventory instrumentation differs from executed construction')
    map_hash = sha(original/'road.xodr')
    xml = ET.parse(original/'road.xodr').getroot()
    if xml.findall('.//signal') or xml.findall('.//signalReference'):
        raise ValueError('Uncontrolled native inventory contradicts map signal definitions')
    rows = [json.loads(line) for line in stream.read_text().splitlines()]
    if len(rows) != len(telemetry):
        raise ValueError('Native control inventory misses original frames')
    scope = json.loads(topology.read_text())
    if (scope.get('schema')!='native-incoming-lane-topology-v1'
            or scope.get('map_sha256')!=map_hash
            or scope.get('instrumentation_sha256')!=implementation_sha):
        raise ValueError('Native lane topology has wrong source provenance')
    connections = {(int(c.attrib['incomingRoad']),int(l.attrib['from']),int(c.attrib['connectingRoad']))
                   for j in xml.findall('junction') for c in j.findall('connection') for l in c.findall('laneLink')}
    native = scope.get('connections', [])
    if not connections or {(c['incoming_road'],c['incoming_lane'],c['connecting_road']) for c in native} != connections:
        raise ValueError('Native lane topology does not cover every incoming connection')
    by_id = {r['id']:r for r in regions}
    expected = {}
    for c in native:
        if not c.get('incoming_observed') or not c.get('connected_junction_observed'):
            raise ValueError('Unobserved native incoming-lane connection')
        road = next(r for r in xml.findall('road') if int(r.attrib['id'])==c['incoming_road'])
        section = len(road.findall('./lanes/laneSection'))-1 if c['incoming_lane']<0 else 0
        region = lane_ids.get((c['incoming_road'],section,c['incoming_lane']))
        if region is None or by_id[region].get('lane',{}).get('enters_intersection') is None:
            raise ValueError('Incoming native lane lost its Core intersection reference')
        expected[region] = by_id[region]['lane']['enters_intersection']
    observations = {atom:[] for atom in selected}
    stream_hash, topology_hash = sha(stream), sha(topology)
    for row, point in zip(rows, telemetry):
        if (row.get('schema')!='native-control-inventory-v1' or row.get('frame')!=point['frame']
                or row.get('time_s')!=point['time_s'] or row.get('map_sha256')!=map_hash
                or row.get('instrumentation_sha256')!=implementation_sha
                or row.get('scope')!='entire_recorded_world'
                or row.get('map_name')!='Carla/Maps/OpenDriveMap'
                or row.get('api_queries')!=['World.get_actors','World.get_environment_objects:TrafficLight','World.get_environment_objects:TrafficSigns']):
            raise ValueError('Native control inventory has incomplete frame, scope or source joins')
        if any(row.get(k) != [] for k in ('traffic_actor_inventory','environment_light_inventory','environment_sign_inventory','unclassified_actor_types')):
            raise ValueError('Native signal absence is unknown or contradicted by observed entities')
        common={'frame':point['frame'],'map_sha256':map_hash,'source_stream':str(stream),
                'source_sha256':stream_hash,'instrumentation_sha256':implementation_sha,
                'scope':'entire_recorded_world','official_authority':'not inferred'}
        if 'dev.traffic_signal' in selected:
            observations['dev.traffic_signal'].append(dict(common,status='verified_absent',
                evidence='Original global native actor, signal-assembly and sign inventories; no unclassified actors; generated native map contains no signal definitions.'))
        if 'st.lane_enters' in selected:
            observations['st.lane_enters'].append(dict(common,status='observed_entry_topology',
                incoming_core_entries={str(k):v for k,v in expected.items()},topology_sha256=topology_hash,
                coverage='Every original native junction incoming lane link; outgoing and internal connector lanes are not asserted to enter an intersection.'))
    return observations


def project(scene, atom, record):
    record = dict(record)
    if record['frame'] is None:
        raise ValueError('Native control observation has no original frame')
    if atom=='dev.traffic_signal':
        if record['status']!='verified_absent' or any(d['kind']=='traffic_signal' for d in scene['devices']):
            raise ValueError('Native signal absence contradicts Core devices')
    elif atom=='st.lane_enters':
        lanes = {str(r['id']):r for r in scene['structures'] if r['kind']=='lane'}
        expected = record['incoming_core_entries']
        applicability=record.get('entry_applicability')
        if applicability is not None:
            if set(applicability)!=set(lanes) or any(lanes[k].get('lane',{}).get('enters_intersection')!=v for k,v in applicability.items()):
                raise ValueError('Delivered lane entry applicability differs from native source scope')
        if (not expected and applicability is None) or any(k not in lanes or lanes[k].get('lane',{}).get('enters_intersection')!=v for k,v in expected.items()):
            raise ValueError('Core incoming-lane topology differs from original native evidence')
    else:
        raise ValueError('Unsupported native control observation')
    return record


def read_lane_sections(original,telemetry,lane_ids,regions,native_facts):
    """Validate native section readbacks and derive entry applicability, not devices."""
    original=Path(original);packet=native_facts.get('native_lane_topology')
    if packet is None or packet.get('complete')is not True:return {}
    if packet.get('schema')!='native-lane-section-readback-v1' or packet.get('api')!='Map.get_waypoint_xodr' or packet.get('errors') or packet.get('map_sha256')!=sha(original/'road.xodr'):
        raise ValueError('Invalid source-bound native lane readback')
    xml=ET.parse(original/'road.xodr').getroot();expected={};roads={}
    for road in xml.findall('road'):
        rid=int(road.get('id'));roads[rid]=road;sections=road.findall('./lanes/laneSection')
        for index,section in enumerate(sections):
            start=float(section.get('s'));end=float(sections[index+1].get('s'))if index+1<len(sections)else float(road.get('length'))
            for lane in section.findall('./left/lane')+section.findall('./right/lane'):
                if lane.get('type')=='driving':expected[(rid,index,int(lane.get('id')))]=(start,end,int(road.get('junction','-1')))
    seen=set()
    for record in packet.get('lanes',[]):
        identity=record.get('identity',[])
        if len(identity)!=3 or any(type(v)is not int for v in identity):raise ValueError('Invalid native lane identity')
        key=tuple(identity)
        if key not in expected or key in seen:raise ValueError('Duplicate or extraneous native lane readback')
        seen.add(key);start,end,junction=expected[key];margin=min(1e-4,(end-start)/4)
        stations=sorted({start+margin,(start+end)/2,end-margin});samples=record.get('samples',[])
        if record.get('station_interval_m')!=[start,end] or [v.get('s_m')for v in samples]!=stations:raise ValueError('Incomplete native lane station coverage')
        for sample in samples:
            if sample.get('native_identity')!=identity or sample.get('is_junction')is not (junction>=0) or sample.get('junction_id')!=(junction if junction>=0 else None):raise ValueError('Native junction readback contradicts map')
    if seen!=set(expected):raise ValueError('Native lane readback does not cover source driving sections')
    incoming=set()
    for junction in xml.findall('junction'):
        for connection in junction.findall('connection'):
            rid=int(connection.get('incomingRoad'))
            if rid not in roads:raise ValueError('Missing source incoming road')
            for link in connection.findall('laneLink'):
                lid=int(link.get('from'));section=len(roads[rid].findall('./lanes/laneSection'))-1 if lid<0 else 0
                key=(rid,section,lid)
                if key in expected:incoming.add(key)
    by_id={r['id']:r for r in regions};applicability={}
    for key in expected:
        ident=lane_ids.get(key)
        if ident is None:return {}  # Unrepresented source lane; no completeness receipt.
        value=by_id[ident].get('lane',{}).get('enters_intersection')
        if key in incoming and value is None:return {}  # Scalar Core join remains unresolved.
        if key not in incoming and value is not None:raise ValueError('Nonincoming source lane has a Core entry assertion')
        applicability[str(ident)]=value
    if set(applicability)!={str(r['id'])for r in regions if r['kind']=='lane'}:return {}
    facts=original/'capture/native_map_facts.json'
    common={'status':'observed_entry_topology','map_sha256':packet['map_sha256'],
        'source':'native_lane_section_readback','source_sha256':sha(facts),
        'incoming_core_entries':{k:v for k,v in applicability.items()if v is not None},
        'entry_applicability':applicability,'scope':'every source driving-lane section; explicit incoming connection list'}
    return {'st.lane_enters':[dict(common,frame=row['frame'])for row in telemetry]}
