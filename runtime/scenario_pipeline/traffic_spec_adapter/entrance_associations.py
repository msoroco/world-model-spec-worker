"""Project observed stop controls and map topology onto painted entrance marks.

The result is deliberately partial.  A nearby line is not by itself evidence
that it marks a particular lane's entrance.  Missing or ambiguous evidence
leaves ``entrance_of`` omitted, never an invented empty list.
"""
import hashlib
import json
import math

from shapely.geometry import MultiPoint, Point

CONTROL_SCOPE = ('all original live traffic light and stop-sign actors; '
                 'stop waypoints and trigger geometry captured in this frame')
MAX_CONTROL_LINE_GAP_M = 8.0
MIN_NEAREST_SEPARATION_M = 0.5
LANE_TOUCH_TOLERANCE_M = 0.15


def _point(native):
    if not isinstance(native, list) or len(native) < 2 or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            for v in native[:2]):
        raise ValueError('Invalid recorded control point')
    return Point(float(native[0]), -float(native[1]))


def _trigger(device):
    vertices = device.get('trigger_vertices_m')
    if not isinstance(vertices, list) or len(vertices) != 8:
        raise ValueError('Stop-sign trigger geometry is missing or incomplete')
    polygon = MultiPoint([_point(v) for v in vertices]).convex_hull
    if polygon.geom_type != 'Polygon' or not polygon.is_valid or polygon.area <= 0:
        raise ValueError('Invalid observed stop-sign trigger')
    return polygon


def _controls(devices, lane_ids, incoming, polygons, by_id):
    by_lane = {lane: [] for lane in incoming}
    actors = set()
    for device in devices:
        actor = device.get('actor_id')
        if type(actor) is not int or actor in actors:
            raise ValueError('Missing or duplicate original control actor ID')
        actors.add(actor)
        kind = device.get('blueprint', '')
        if kind.startswith('traffic.traffic_light'):
            waypoints = device.get('stop_waypoints')
            if not isinstance(waypoints, list):
                raise ValueError('Traffic-light stop waypoints were not captured')
            for waypoint in waypoints:
                key = tuple(waypoint.get(k) for k in ('road_id', 'section_id', 'lane_id'))
                lane = lane_ids.get(key)
                if lane in by_lane:
                    by_lane[lane].append({'kind': 'light_stop_waypoint', 'actor_id': actor,
                                          'shape': _point(waypoint.get('position_m'))})
        elif kind.startswith('traffic.stop'):
            trigger = _trigger(device)
            for lane in incoming:
                if any(shape.intersects(trigger) for shape in _approach_shapes(lane, by_id, polygons)):
                    by_lane[lane].append({'kind': 'stop_sign_trigger', 'actor_id': actor,
                                          'shape': trigger})
    return by_lane


def _approach_shapes(lane, by_id, polygons):
    """The incoming lane and its immediate mapped junction continuations."""
    linked = by_id[lane].get('lane', {}).get('leads_to', [])
    return [polygons[ident] for ident in [lane, *linked] if ident in polygons]


def _crosswalk(region, shape, incoming, polygons, by_id, native_keys):
    candidates = set()
    for lane in incoming:
        linked = by_id[lane]['lane'].get('leads_to', [])
        # A polygon touching a neighbouring approach at one corner is not a
        # crosswalk across that approach.  Require positive shared area.
        if shape.intersection(polygons[lane]).area > 1e-4 or any(
                target in polygons and shape.intersection(polygons[target]).area > 1e-4
                for target in linked):
            candidates.add(lane)
    junctions = {by_id[lane]['lane']['enters_intersection'] for lane in candidates}
    if not candidates:
        return None, 'no map-proven incoming approach'
    if any(lane not in native_keys for lane in candidates):
        return None, 'incoming lane has no unique retained native identity; existing entrance evidence is preserved'
    approaches = {native_keys[lane][0] for lane in candidates}
    if len(junctions) != 1 or len(approaches) != 1:
        return None, 'crosswalk spans ambiguous entrance approaches'
    return sorted(candidates), 'unique incoming approach from map lane connectivity'


def _state(regions, polygons, lane_ids, painted, devices):
    by_id = {r['id']: r for r in regions}
    native_keys = {core: native for native, core in lane_ids.items()}
    incoming = {r['id'] for r in regions if r['kind'] in
                ('lane', 'turn_lane', 'reserved_lane', 'centre_turn_lane')
                and r.get('lane', {}).get('enters_intersection') is not None}
    controls = _controls(devices, lane_ids, incoming, polygons, by_id)
    lines = [item for item in painted if item['region']['kind'] == 'stop_line']
    nearest = {}
    for lane in incoming:
        options = []
        approach = _approach_shapes(lane, by_id, polygons)
        for line in lines:
            shape = line['shape']
            if not any(shape.distance(part) <= LANE_TOUCH_TOLERANCE_M for part in approach):
                continue
            for control in controls[lane]:
                gap = shape.distance(control['shape'])
                if gap <= MAX_CONTROL_LINE_GAP_M:
                    options.append((gap, line['region']['id'], control['actor_id'], control['kind']))
        options.sort()
        if options:
            best = options[0]
            rival = next((option for option in options if option[1] != best[1]), None)
            if rival is None or rival[0] - best[0] >= MIN_NEAREST_SEPARATION_M:
                nearest[lane] = best
    associations, receipts = {}, []
    for item in painted:
        region = item['region']
        ident, kind = region['id'], region['kind']
        if kind == 'crosswalk':
            selected, reason = _crosswalk(region, item['shape'], incoming, polygons, by_id, native_keys)
            controls_used = []
        else:
            crossed = {lane for lane in incoming if any(
                item['shape'].distance(control['shape']) <= MAX_CONTROL_LINE_GAP_M
                for control in controls[lane]) and any(
                item['shape'].distance(part) <= LANE_TOUCH_TOLERANCE_M
                for part in _approach_shapes(lane, by_id, polygons))}
            selected = sorted(lane for lane in crossed if lane in nearest and nearest[lane][1] == ident)
            controls_used = sorted({nearest[lane][2] for lane in selected})
            if not crossed:
                selected, reason = None, 'no observed incoming lane crossing this line'
            elif set(selected) != crossed:
                selected, reason = None, 'stop control or unique line match missing for a crossed lane'
            elif len({by_id[lane]['lane']['enters_intersection'] for lane in selected}) != 1:
                selected, reason = None, 'line crosses lanes entering different intersections'
            else:
                reason = 'unique recorded stop control and painted-line map join'
        if selected is not None:
            associations[ident] = selected
        receipts.append({'region_id': ident, 'kind': kind,
                         'native_road_id': item['source']['road_id'],
                         'native_object_id': item['source']['object_id'],
                         'status': 'associated' if selected is not None else 'unknown',
                         'entrance_of': selected, 'control_actor_ids': controls_used,
                         'reason': reason})
    return associations, receipts


def project(regions, polygons, lane_ids, painted, evidence):
    """Return per-frame known associations and hash-addressed state receipts."""
    if not evidence:
        raise ValueError('Entrance association requires original frames')
    states, frames = {}, []
    for event in evidence:
        observed = event.get('original_observations', {})
        if observed.get('frame') != event.get('original_frame') or observed.get('control_inventory') != CONTROL_SCOPE:
            raise ValueError('Incomplete same-frame entrance-control inventory')
        devices = [d for d in observed.get('devices', []) if
                   d.get('blueprint', '').startswith(('traffic.traffic_light', 'traffic.stop'))]
        geometry = [{key: d[key] for key in ('actor_id', 'blueprint', 'position_m',
                     'stop_waypoints', 'trigger_vertices_m') if key in d} for d in devices]
        state = json.dumps(geometry, sort_keys=True, separators=(',', ':'), allow_nan=False)
        digest = hashlib.sha256(state.encode()).hexdigest()
        if digest not in states:
            associations, receipts = _state(regions, polygons, lane_ids, painted, devices)
            states[digest] = {'associations': associations, 'receipts': receipts,
                              'control_actor_ids': [d['actor_id'] for d in devices]}
        frames.append({'frame': event['original_frame'], 'state_sha256': digest,
                       'associations': states[digest]['associations']})
    return {'frames': frames, 'states': states,
            'method': 'observed CARLA stop waypoints or stop-sign trigger plus native map topology; '
                      'crosswalk map connectivity must identify one approach'}


def resolve_case_references(config, painted, frame_count, required):
    """Freeze case-relevant native map-object IDs, not chosen conversion outcomes."""
    source = config.get('required_entrance_references')
    if source is None:
        source = []
    if not isinstance(source, list) or (required and not source):
        raise ValueError('Required entrance atom needs declared native object references')
    lookup = {}
    for item in painted:
        key = (item['source']['road_id'], str(item['source']['object_id']))
        if key in lookup:
            raise ValueError('Duplicate native painted-object identity')
        lookup[key] = item['region']
    resolved = []
    seen = set()
    for ref in source:
        if not isinstance(ref, dict) or set(ref) != {'road_id', 'object_id', 'start_frame', 'end_frame'}:
            raise ValueError('Entrance reference needs road_id, object_id and exact frame interval')
        road, object_id = ref['road_id'], str(ref['object_id'])
        start, end = ref['start_frame'], ref['end_frame']
        if type(road) is not int or type(start) is not int or type(end) is not int or not 0 <= start <= end < frame_count:
            raise ValueError('Invalid entrance reference identity or frame interval')
        key = (road, object_id)
        if key in seen or key not in lookup:
            raise ValueError('Duplicate or missing case-relevant entrance object')
        seen.add(key)
        region = lookup[key]
        if region['kind'] not in ('stop_line', 'crosswalk'):
            raise ValueError('Case entrance reference is not a line or crosswalk')
        resolved.append(dict(ref, object_id=object_id, region_id=region['id']))
    return resolved


def retained_associations(evidence, scene, lane_ids):
    """Recover positive map joins even when old captures lack inventory markers.

    Map-only crosswalk joins do not need a control inventory. Stop lines still
    require the complete measured control geometry used by the normal exporter.
    """
    from .geometry import painted_map_objects, match_regions
    from shapely.geometry import Polygon, LineString
    path=evidence.path('road.xodr')
    if path is None:return {}, ['No integrity-bound map for entrance projection']
    painted=painted_map_objects(path)
    matches=match_regions([p['region'] | {'id':i+1} for i,p in enumerate(painted)],scene['structures'])
    selected=[]
    for i,item in enumerate(painted,1):
        if i in matches:
            item['region']['id']=matches[i];selected.append(item)
    if not selected:return {}, []
    polygons={}
    for r in scene['structures']:
        b=r.get('boundary')
        if not b or len(b)<2:continue
        shape=Polygon(b) if len(b)>=3 else LineString(b)
        if shape.is_valid:polygons[r['id']]=shape
    result,issues={},[]
    events=evidence.rows('capture/evidence.jsonl')
    crosswalks=[p for p in selected if p['region']['kind']=='crosswalk']
    static,_=_state(scene['structures'],polygons,lane_ids,crosswalks,[])
    result['static']=static
    if events and all(e.get('original_observations',{}).get('control_inventory')==CONTROL_SCOPE for e in events):
        projection=project(scene['structures'],polygons,lane_ids,selected,events)
        for event,frame in zip(events,projection['frames']):
            result[round(event['recording_time_s']*1000)]=frame['associations']
    else:
        # Older captures can retain positive stop-waypoint/trigger measurements
        # without the newer global inventory marker. They establish positive
        # joins only, never an empty inventory or a negative association.
        devices_by_time={}
        for event in events:
            observed=event.get('original_observations',{})
            if observed.get('frame')!=event.get('original_frame'):continue
            devices=[d for d in observed.get('devices',[]) if
                (d.get('blueprint','').startswith('traffic.traffic_light') and isinstance(d.get('stop_waypoints'),list)) or
                (d.get('blueprint','').startswith('traffic.stop') and isinstance(d.get('trigger_vertices_m'),list))]
            if devices:devices_by_time.setdefault(round(event['recording_time_s']*1000),[]).extend(devices)
        for row in evidence.rows('signal_governing_relationship.jsonl'):
            value=row.get('value',{}).get('signal',{})
            if not value.get('lane_association_verified') or not isinstance(value.get('stop_waypoints'),list):continue
            record={'actor_id':value.get('actor_id'),'blueprint':value.get('type_id'),
                    'position_m':value.get('transform',{}).get('position_m'),'stop_waypoints':[]}
            for waypoint in value['stop_waypoints']:
                item=dict(waypoint)
                if 'position_m' not in item:item['position_m']=item.get('transform',{}).get('position_m')
                record['stop_waypoints'].append(item)
            devices_by_time.setdefault(round(row['time_s']*1000),[]).append(record)
        for stamp,devices in devices_by_time.items():
            # Repeated independently recorded controls must agree on geometry.
            unique={};ambiguous=set()
            for device in devices:
                actor=device['actor_id']
                relevant={k:device[k] for k in ('actor_id','blueprint','stop_waypoints','trigger_vertices_m') if k in device}
                if 'stop_waypoints' in relevant:
                    relevant['stop_waypoints']=[{k:point.get(k) for k in ('road_id','section_id','lane_id','position_m')} for point in relevant['stop_waypoints']]
                if actor in unique and unique[actor][0]!=relevant:ambiguous.add(actor)
                else:unique[actor]=(relevant,device)
            observed=[device for actor,(_,device) in unique.items() if actor not in ambiguous]
            if observed:
                associations,_=_state(scene['structures'],polygons,lane_ids,selected,observed)
                # Core stores a closed list. A partial control packet must not
                # turn an unmeasured neighbouring entrance into definite false.
                by_id={r['id']:r for r in scene['structures']}
                incoming={r['id'] for r in scene['structures'] if r.get('lane',{}).get('enters_intersection') is not None}
                for item in selected:
                    ident=item['region']['id']
                    if item['region']['kind']!='stop_line' or ident not in associations:continue
                    possible={lane for lane in incoming if any(item['shape'].distance(shape)<=LANE_TOUCH_TOLERANCE_M for shape in _approach_shapes(lane,by_id,polygons))}
                    if possible-set(associations[ident]):associations.pop(ident)
                result[stamp]={k:v for k,v in associations.items() if v}
        lines={p['region']['id'] for p in selected if p['region']['kind']=='stop_line'}
        unresolved={ident for ident in lines if 'entrance_of' not in next(r for r in scene['structures'] if r['id']==ident)
                    and any(ident not in result.get(round(e['recording_time_s']*1000),{}) for e in events)}
        if unresolved:issues.append('Stop-line entrance remains unknown in some frames after checking original stop-waypoint/trigger packets and retained governance sidecars')
    return result,issues
