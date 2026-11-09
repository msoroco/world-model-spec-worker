"""Static package definition shared by the generator and the CPU tests (no CARLA)."""
import scenario as S

AID = 'testing__C101303__NRS-484B-127-1__motor_vehicle_driver'
LAW, CELL, ACTOR = 'NRS-484B-127-1', 'C101303', 'motor_vehicle_driver'
CASES = list(S.VARIANTS)
REQUIRED_ATOMS = ['ru.subject', 'kin.speed', 'kin.position', 'rel.ahead_behind_in_lane', 'rel.surface_gap', 'st.lane', 'st.crest', 'st.grade']


def case_id(variant):
    return AID + '__' + variant


def channel(name, unit, method, uncertainty):
    return {'name': name, 'unit': unit, 'method': method, 'time_window': 'full recording, every tick', 'sampling_rate_hz': S.RATE_HZ,
            'reference_frame': 'road frame (s along lane direction, lane ids from native waypoint readback)', 'uncertainty': uncertainty}


def recording_description():
    return {'channels': [
        channel('ego_speed_mps', 'm/s', 'Native actor.get_velocity magnitude each tick', 'engine velocity; no sensor noise model'),
        channel('lead_speed_mps', 'm/s', 'Native actor.get_velocity magnitude of the control (lead) vehicle each tick', 'engine velocity'),
        channel('bumper_gap_m', 'm', 'Road-frame distance from lead rear to ego front while the lead is ahead in the ego lane; -1 when none', 'nominal bounding-box length; straight road so s equals x'),
        channel('ego_lane_id', 'lane id', 'Native waypoint lane_id readback at ego location', 'lane assignment by native map projection')],
        'context_inputs': [{'name': 'surface_context', 'unit': 'structured record', 'method': 'authored world setup plus native readback (wetness, friction, grade, crest, public-way declaration)'}],
        'limitations': ['Reasonable and prudent following distance is a legal judgment and is not measured.',
                        'Public-way status is an authored declaration of a synthetic road.',
                        'Tire friction is an engine setting, not a measured real-world coefficient.']}


def measurement_inputs():
    s = ['following_samples.jsonl']
    return {'public_way_context': {'method': 'public_way_context', 'inputs': ['surface_context.json', 'following_samples.jsonl']},
            'ego_lead_speeds': {'method': 'speed_profile', 'inputs': s}, 'following_separation': {'method': 'separation_profile', 'inputs': s},
            'surrounding_traffic': {'method': 'surrounding_traffic', 'inputs': ['surface_context.json'] + s},
            'highway_condition': {'method': 'highway_condition', 'inputs': ['surface_context.json'] + s},
            'following_interval_before_lane_change': {'method': 'following_interval', 'inputs': s},
            'lane_change_route_crest': {'method': 'lane_change_route', 'inputs': ['surface_context.json'] + s},
            'qualifying_vehicle_motion': {'method': 'qualifying_motion', 'inputs': ['surface_context.json'] + s}}


def camera_list():
    return [{'name': 'overview', 'width': 1920, 'height': 1080, 'fov_deg': 70, 'pose_strategy': 'airborne chase of the ego/lead midpoint, 45 m up, pitched 60 degrees down'},
            {'name': 'approach', 'width': 1280, 'height': 720, 'fov_deg': 80, 'pose_strategy': 'trailing 12 m behind and 3.2 m above ego, looking forward'},
            {'name': 'reference_corner', 'width': 1280, 'height': 720, 'fov_deg': 80, 'pose_strategy': 'right-side corner view 12 m beside ego, aimed at the vehicles'},
            {'name': 'driver_reference', 'width': 1280, 'height': 720, 'fov_deg': 90, 'pose_strategy': 'driver eye point in ego cabin, forward'}]


def config_for(variant, supported=None):
    params = S.case_params(variant)
    cid = case_id(variant)
    return {'law_id': LAW, 'cell_id': CELL, 'actor': ACTOR, 'selected_case_id': cid, 'supported_case_ids': supported or [case_id(v) for v in CASES],
            'case': {'case_id': cid, 'recording_description': recording_description()}, 'case_parameters': params,
            'required_atoms': REQUIRED_ATOMS, 'source_packets': [], 'rate_hz': S.RATE_HZ, 'duration_s': params['duration_s'],
            'cameras': camera_list(), 'public_way_road_ids': [S.ROAD_ID], 'measurement_inputs': measurement_inputs()}
