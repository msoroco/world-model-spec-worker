"""Commercial service parking construction and original input measurements.

No engineering distance is asserted to define an immediate neighborhood.
"""
from dataclasses import dataclass, replace
from math import hypot, isfinite


@dataclass(frozen=True)
class Case:
    name: str
    work_kind: str = 'service'
    work_near: bool = True
    length_ft: float = 24.0
    unladen_lb: float = 8001.0
    adjacent_kind: str = 'public_school'
    frontage_ft: float = 300.0
    posted_permission: bool = False
    loading: bool = False


BASE = Case('service_school_24ft_8001lb')
CASES = (
    BASE,
    replace(BASE, name='no_service', work_kind='none'),
    replace(BASE, name='repair_near', work_kind='repair'),
    replace(BASE, name='construction_near', work_kind='construction'),
    replace(BASE, name='similar_essential_near', work_kind='similar_essential'),
    replace(BASE, name='service_far', work_near=False),
    replace(BASE, name='posted_permission', posted_permission=True),
    replace(BASE, name='expeditious_loading', loading=True, work_kind='none'),
    replace(BASE, name='length_23_9ft', length_ft=23.9, unladen_lb=7999.0),
    replace(BASE, name='length_24_0ft', unladen_lb=7999.0),
    replace(BASE, name='length_24_1ft', length_ft=24.1, unladen_lb=7999.0),
    replace(BASE, name='weight_7999lb', length_ft=23.9, unladen_lb=7999.0),
    replace(BASE, name='weight_8000lb', length_ft=23.9, unladen_lb=8000.0),
    replace(BASE, name='weight_8001lb', length_ft=23.9, unladen_lb=8001.0),
    replace(BASE, name='residence_299ft', adjacent_kind='residence', frontage_ft=299.0),
    replace(BASE, name='residence_300ft', adjacent_kind='residence', frontage_ft=300.0),
    replace(BASE, name='residence_301ft', adjacent_kind='residence', frontage_ft=301.0),
    replace(BASE, name='public_park', adjacent_kind='public_park'),
)

SOURCE_FIELDS = ('street_public_access', 'city_jurisdiction', 'school_public_status',
    'school_or_park_adjacency', 'residential_frontage', 'business_district_exclusion',
    'commercial_vehicle_classification', 'overall_length', 'unladen_weight',
    'parking_device_exact_text', 'posted_permission_authority', 'governed_curb',
    'vehicle_parking_motion', 'worksite_location', 'work_order_and_activity',
    'vehicle_work_relationship', 'loading_activity', 'section_wide_exceptions')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(v):
    return type(v) in (int, float) and isfinite(v)


def point(v):
    return isinstance(v, (list, tuple)) and len(v) == 2 and all(number(x) for x in v)


def rectangle(v):
    return isinstance(v, (list, tuple)) and len(v) == 4 and all(number(x) for x in v) and v[0] < v[2] and v[1] < v[3]


def distance(a, b):
    require(point(a) and point(b), 'vehicle/worksite positions missing')
    return hypot(a[0]-b[0], a[1]-b[1])


def overlap(a, b):
    require(rectangle(a) and rectangle(b), 'original footprint or governed curb missing')
    return max(0., min(a[2], b[2])-max(a[0], b[0])) * max(0., min(a[3], b[3])-max(a[1], b[1]))


def validate_scene(scene, case):
    require(case in CASES, 'unknown service-parking case')
    require(scene.get('cell_id') == 'C229439' and scene.get('actor') == 'heavy_vehicle_driver', 'cell/actor changed')
    require(all(scene.get(k) for k in ('vehicle_id','driver_id','worker_id','heavy_vehicle_blueprint','work_order_id','work_activity_description','parking_device_text')), 'participant, work or device identity missing')
    require(scene.get('commercial_vehicle') is True and scene.get('street_public') is True and scene.get('city_jurisdiction') is True, 'commercial/public-street/city source missing')
    require(scene.get('adjacent_kind') == case.adjacent_kind, 'adjacent place changed')
    if case.adjacent_kind == 'public_school':
        require(scene.get('school_public') is True, 'public school status missing')
    if case.adjacent_kind == 'residence':
        require(scene.get('business_district') is False and scene.get('mainly_residential') is True, 'residence district source missing')
    for key in ('work_kind','work_near','length_ft','unladen_lb','adjacent_kind','frontage_ft','posted_permission','loading'):
        require(scene.get(key) == getattr(case,key), 'case parameter changed: '+key)
    require(number(scene['length_ft']) and scene['length_ft'] > 0 and number(scene['unladen_lb']) and scene['unladen_lb'] > 0 and number(scene['frontage_ft']) and scene['frontage_ft'] >= 0, 'numeric source invalid')
    require(rectangle(scene.get('governed_curb_rect_m')) and rectangle(scene.get('vehicle_footprint_rect_m')) and overlap(scene['governed_curb_rect_m'],scene['vehicle_footprint_rect_m']) > 0, 'parked footprint misses governed curb')
    require(point(scene.get('vehicle_center_xy')) and point(scene.get('worksite_xy')), 'worksite geometry missing')
    require((distance(scene['vehicle_center_xy'],scene['worksite_xy']) < 80) is case.work_near, 'engineering near/far placement changed')
    require(isinstance(scene.get('parking_route_xy'),list) and len(scene['parking_route_xy']) >= 2 and all(point(x) for x in scene['parking_route_xy']), 'parking route missing')
    require(type(scene.get('park_start_frame')) is int and 0 <= scene['park_start_frame'] < 900, 'parked interval missing')
    for field in SOURCE_FIELDS:
        require(scene.get(field+'_source_sha256'), 'reviewed source missing: '+field)
    return {'case_id':case.name,'legal_judgment':None,'immediate_neighborhood_judgment':None,'modifier_scope_judgment':None}


def construct(adapter, scene, case):
    context=validate_scene(scene,case); owned=[]
    try:
        for actor in (adapter.spawn_device(scene['parking_device_text'],scene['governed_curb_rect_m']),
                      adapter.spawn_vehicle(scene['parking_route_xy'][0],scene['heavy_vehicle_blueprint']),
                      adapter.spawn_worksite(scene['worksite_xy'],scene['work_activity_description']),
                      adapter.spawn_worker(scene['worksite_xy'],scene['worker_id'])):
            require(actor is not None, 'Native participant/device creation failed')
            owned.append(actor)
        adapter.set_parking_route(owned[1],scene['parking_route_xy'],scene['park_start_frame'])
        adapter.set_work_activity(owned[2],owned[3],scene['work_kind'],scene['work_order_id'])
        return {'owned':tuple(owned),'vehicle':owned[1],'worksite':owned[2],'worker':owned[3],**context}
    except Exception:
        for actor in reversed(owned): adapter.destroy(actor)
        raise


def measure_original(rows, scene, case, *, diagnostic_frames=None):
    validate_scene(scene,case)
    expected=diagnostic_frames if diagnostic_frames is not None else 900
    require(len(rows)==expected and expected>=3,'complete original trace missing')
    first=rows[0].get('original_frame'); t0=rows[0].get('time_s')
    require(type(first) is int and number(t0),'original frame/time missing')
    parked=[]; active=[]; distances=[]; overlaps=[]
    for i,row in enumerate(rows):
        require(row.get('original_frame')==first+i and number(row.get('time_s')) and abs(row['time_s']-t0-i/20)<=.005,'original frame/time join differs')
        for field in SOURCE_FIELDS:
            require(row.get(field+'_source_sha256')==scene[field+'_source_sha256'],'source context changed: '+field)
        for key in ('vehicle_id','driver_id','worker_id','work_kind','length_ft','unladen_lb','adjacent_kind','frontage_ft','posted_permission','loading'):
            require(row.get(key)==scene[key],'original input changed: '+key)
        require(number(row.get('speed_mps')) and row['speed_mps']>=0 and rectangle(row.get('vehicle_footprint_rect_m')) and point(row.get('vehicle_center_xy')) and point(row.get('worksite_xy')) and type(row.get('work_active')) is bool,'parking/work readback missing')
        if i>=scene['park_start_frame']:
            parked.append(row['speed_mps']<=.1)
            active.append(row['work_active'])
            distances.append(distance(row['vehicle_center_xy'],row['worksite_xy']))
            overlaps.append(overlap(row['vehicle_footprint_rect_m'],scene['governed_curb_rect_m'])>0)
    require(parked and all(parked) and all(overlaps),'vehicle did not park at governed curb')
    require(all(active) if case.work_kind!='none' else not any(active),'actual work activity differs')
    return {'parked_frames':len(parked),'work_active_all_parked_frames':all(active),
            'work_distance_m_min':min(distances),'work_distance_m_max':max(distances),
            'length_ft':scene['length_ft'],'unladen_lb':scene['unladen_lb'],
            'residential_frontage_ft':scene['frontage_ft'],'adjacent_kind':scene['adjacent_kind'],
            'posted_permission':scene['posted_permission'],'loading':scene['loading'],
            'legal_judgment':None,'immediate_neighborhood_judgment':None,'modifier_scope_judgment':None}
