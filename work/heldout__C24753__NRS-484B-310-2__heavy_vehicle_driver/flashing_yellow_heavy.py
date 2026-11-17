"""Heavy-vehicle flashing-yellow scene request and source-shaped observation.

An adapter must implement these creation/readback operations in the Native runner.
The chosen speeds and blink period are engineering inputs, not legal thresholds.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import hypot, cos, sin, radians

@dataclass(frozen=True)
class Case:
    name: str
    direction: str
    target_mps: float
    crossing_vehicle: bool

CASES={
    'east_cautious_proxy':Case('east_cautious_proxy','east',3.0,True),
    'east_faster_proxy':Case('east_faster_proxy','east',7.0,True),
    'east_no_crossing':Case('east_no_crossing','east',3.0,False),
    'west_cautious_proxy':Case('west_cautious_proxy','west',3.0,True),
}

def lamp_on(time_s,cycle_s=.5):
    if time_s<0 or cycle_s<=0:raise ValueError('invalid lamp timing')
    return time_s%cycle_s<cycle_s/2

def construct(adapter,case):
    if case.direction not in ('east','west'):raise ValueError('unsupported approach direction')
    intersection=adapter.intersection(layout='blind_intersection',through_lanes=2,cross_lanes=2)
    sign=-1 if case.direction=='east' else 1
    start,end=(sign*70.0,0.0),(-sign*70.0,0.0)
    head=adapter.signal_head(lens='yellow',illuminated=True,governs_approach=case.direction,
                             mounted_xy=(sign*12.0,-sign*3.0))
    device=adapter.official_control_device(type='flashing_yellow',linked_signal=head)
    ego=adapter.vehicle(role='ego',vehicle_class='heavy_vehicle',route=[start,end],target_mps=case.target_mps)
    crossing=None
    if case.crossing_vehicle:
        crossing=adapter.vehicle(role='crossing',vehicle_class='motor_vehicle',route=[(0,-65),(0,65)],target_mps=5)
    return {'intersection':intersection,'signal_head':head,'official_device':device,'ego':ego,'crossing':crossing}

def measure(samples):
    if len(samples)<10:raise ValueError('at least ten original 20 Hz samples required')
    rows=[]
    for i,s in enumerate(samples):
        if abs(s.get('time_s',-1)-i*.05)>.005:raise ValueError('non-20Hz original time')
        if s.get('signal_head_visible') is not True or type(s.get('yellow_lens_on')) is not bool:
            raise ValueError('missing physical yellow signal readback')
        if not s.get('official_device_source') or not s.get('signal_source') or not s.get('ego_source'):
            raise ValueError('original device, signal or heavy-vehicle source missing')
        if s.get('ego_vehicle_class')!='heavy_vehicle' or s.get('approach_direction') not in ('east','west'):
            raise ValueError('heavy subject or approach direction missing')
        if type(s.get('ego_speed_mps')) not in (int,float) or s['ego_speed_mps']<0:
            raise ValueError('original speed sample missing')
        xy=s.get('ego_center_xy')
        if not isinstance(xy,list) or len(xy)!=2:raise ValueError('original ego position missing')
        rows.append({'time_s':s['time_s'],'speed_mps':s['ego_speed_mps'],
                     'distance_to_conflict_m':hypot(*xy),'yellow_lens_on':s['yellow_lens_on'],
                     'approach_direction':s['approach_direction'],
                     'crossing_present':bool(s.get('crossing_source'))})
    if set(r['yellow_lens_on'] for r in rows)!={False,True}:
        raise ValueError('intermittent yellow illumination not observed')
    if len(set(r['approach_direction'] for r in rows))!=1:raise ValueError('approach direction changed within case')
    return {'samples':rows,'vehicle_class':'heavy_vehicle','approach_direction':rows[0]['approach_direction'],
            'min_speed_mps':min(r['speed_mps'] for r in rows),'max_speed_mps':max(r['speed_mps'] for r in rows),
            'crossing_present':any(r['crossing_present'] for r in rows),'legal_caution_judgment':None}

def audit_comparison(a,b,variable):
    if variable not in ('approach_speed','crossing_context','approach_direction'):
        raise ValueError('unknown comparison variable')
    if not a.get('samples') or not b.get('samples'):raise ValueError('original source measurements missing')
    for key in ('map_hash','signal_head_hash','official_device_source','blink_period_s','camera_plan_hash','duration_s','vehicle_class'):
        if not a.get(key) or a[key]!=b.get(key):raise ValueError('fixed condition changed: '+key)
    var={'approach_speed':'target_mps','crossing_context':'crossing_vehicle','approach_direction':'direction'}[variable]
    for key in ('target_mps','crossing_vehicle','direction'):
        if key!=var and a.get(key)!=b.get(key):raise ValueError('undeclared condition changed: '+key)
    if a.get(var)==b.get(var):raise ValueError('deliberate comparison variable did not change')
    return {'comparison_complete':True,'variable':variable,'legal_caution_judgment':None}


def _native_direction(waypoint):
    yaw = radians(float(waypoint.transform.rotation.yaw))
    dx, dy = cos(yaw), sin(yaw)
    if abs(dx) < .75 or abs(dy) > .66:
        return None
    return 'east' if dx > 0 else 'west'


def _native_junction(waypoint):
    cursor = waypoint
    for _ in range(16):
        junction = cursor.get_junction()
        if junction is not None:
            return int(junction.id)
        forward = cursor.next(2.0)
        if len(forward) != 1:
            return None
        cursor = forward[0]
    return None


def discover_native_control(world, official_control_source):
    """Find two distinct map-linked heads at one junction; official status is a premise."""
    if not str(official_control_source or '').strip():
        raise ValueError('missing official-control source premise')
    by_junction = {}
    for light in world.get_actors().filter('traffic.traffic_light*'):
        opendrive = str(light.get_opendrive_id() or '').strip()
        if not opendrive:
            continue
        for waypoint in light.get_affected_lane_waypoints():
            direction = _native_direction(waypoint)
            junction = _native_junction(waypoint)
            if direction and junction is not None:
                by_junction.setdefault(junction, {}).setdefault(direction, []).append(
                    {'light':light,'waypoint':waypoint,'junction_id':junction,
                     'direction':direction,'opendrive_id':opendrive})
    for junction in sorted(by_junction):
        group = by_junction[junction]
        if 'east' in group and 'west' in group:
            east, west = group['east'][0], group['west'][0]
            if east['light'].id != west['light'].id:
                return {'east':east,'west':west}
    raise ValueError('no distinct opposing Native signal heads at one junction')


def _native_route(waypoint, before_m, after_m):
    if before_m <= 0 or after_m <= 0:
        raise ValueError('route distances must be positive')
    before, after = waypoint.previous(before_m), waypoint.next(after_m)
    if len(before) != 1 or len(after) != 1:
        raise ValueError('ambiguous Native route at governed lane')
    return before[0].transform, after[0].transform


def _crossing_route(world_map, junction_id):
    options = []
    for waypoint in world_map.generate_waypoints(5.0):
        if _native_junction(waypoint) != junction_id:
            continue
        yaw = radians(float(waypoint.transform.rotation.yaw))
        if abs(sin(yaw)) < .75 or abs(cos(yaw)) > .66:
            continue
        try:
            start, end = _native_route(waypoint, 65.0, 65.0)
        except ValueError:
            continue
        if abs(float(end.location.y)-float(start.location.y)) < 32.5:
            continue
        options.append((int(waypoint.road_id),int(waypoint.lane_id),start,end))
    if not options:
        raise ValueError('no traversing perpendicular lane at selected junction')
    options.sort(key=lambda x:(x[0],x[1]))
    road,lane,start,end=options[0]
    return {'road_id':road,'lane_id':lane,'start':start,'end':end}


def construct_native(world, case, official_control_source, heavy_blueprint_id,
                     crossing_blueprint_id, *, before_m=70.0):
    """Spawn the actual map-linked actors; the caller owns and destroys returned actors."""
    if case.direction not in ('east','west') or case.target_mps <= 0:
        raise ValueError('invalid heavy-vehicle case')
    if not str(heavy_blueprint_id or '').startswith('vehicle.') or not str(crossing_blueprint_id or '').startswith('vehicle.'):
        raise ValueError('explicit vehicle blueprints required')
    controls = discover_native_control(world, official_control_source)
    selected = controls[case.direction]
    start,end = _native_route(selected['waypoint'],before_m,70.0)
    if (float(end.location.x)-float(start.location.x)) * (1 if case.direction=='east' else -1) <= 0:
        raise ValueError('governed route reverses requested direction')
    crossing_route = _crossing_route(world.get_map(),selected['junction_id']) if case.crossing_vehicle else None
    library = world.get_blueprint_library()
    heavy = library.find(heavy_blueprint_id)
    crossing_blueprint = library.find(crossing_blueprint_id) if crossing_route else None
    owned=[]
    try:
        ego=world.try_spawn_actor(heavy,start)
        if ego is None:
            raise ValueError('heavy Native actor spawn failed')
        owned.append(ego)
        cross=None
        if crossing_route:
            cross=world.try_spawn_actor(crossing_blueprint,crossing_route['start'])
            if cross is None:
                raise ValueError('crossing Native actor spawn failed')
            owned.append(cross)
        return {'controls':controls,'selected':selected,'ego':ego,'crossing':cross,
                'ego_route':(start,end),'crossing_route':crossing_route,'owned':owned,
                'heavy_blueprint_id':heavy_blueprint_id,
                'official_control_source':official_control_source}
    except BaseException:
        for actor in reversed(owned):
            actor.destroy()
        raise


class NativeYellowController:
    """Command and read back the selected physical signal head per capture frame."""
    def __init__(self, light, traffic_light_state, period_s=.5):
        if period_s <= 0:
            raise ValueError('invalid blink period')
        self.light,self.state,self.period_s=light,traffic_light_state,period_s
        self.initial=None

    def __enter__(self):
        self.initial=self.light.get_state()
        return self

    def set_at(self,time_s):
        if self.initial is None:
            raise RuntimeError('signal controller not entered')
        target=self.state.Yellow if lamp_on(time_s,self.period_s) else self.state.Off
        self.light.set_state(target)
        observed=self.light.get_state()
        if observed != target:
            raise ValueError('flashing-yellow Native readback differs')
        return {'frame_time_s':time_s,'yellow_lens_on':target==self.state.Yellow,
                'native_light_state':str(observed),'light_actor_id':int(self.light.id)}

    def __exit__(self,exc_type,exc,tb):
        if self.initial is not None:
            self.light.set_state(self.initial)
            if self.light.get_state()!=self.initial:
                raise ValueError('Native signal restoration readback differs')
            self.initial=None
