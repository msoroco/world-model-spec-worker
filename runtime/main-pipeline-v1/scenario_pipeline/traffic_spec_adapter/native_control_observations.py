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
    from batch_pipeline.completion import verify
    verify(original, binding)
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
        if not expected or any(k not in lanes or lanes[k].get('lane',{}).get('enters_intersection')!=v for k,v in expected.items()):
            raise ValueError('Core incoming-lane topology differs from original native evidence')
    else:
        raise ValueError('Unsupported native control observation')
    return record
