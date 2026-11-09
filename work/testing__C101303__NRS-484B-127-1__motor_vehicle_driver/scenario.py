"""Pure-Python construction for the C101303 hill-crest following scenario.

No CARLA import here. Everything is configuration driven, so the CPU checks can
exercise road generation, case parameters, controllers and a kinematic preview.
Engineering knobs (speeds, authored gaps, trigger positions) are not legal
thresholds; 'reasonable and prudent' is never evaluated by this code.
"""
import math

ROAD_ID = 1
LANE_WIDTH_M = 3.5
ROAD_LENGTH_M = 1200.0
CREST_S_M = 450.0
CREST_VERTICAL_CURVE_M = 120.0
GRADE = 0.03
EGO_LANE, DEST_LANE = -1, -2
RATE_HZ = 20
DT = 1.0 / RATE_HZ
VEHICLE_LENGTH_M = 4.7  # nominal; the runner replaces it with the actual bounding box
EGO_S0_M = 150.0
LANE_CHANGE_TRIGGER_S_M = 420.0
LANE_CHANGE_DURATION_S = 5.0

BASE = {
    'ego_set_speed_mps': 13.4, 'lead_speed_mps': 13.4, 'initial_gap_m': 25.0, 'gap_hold_m': 25.0,
    'lead_event': None,  # None | {'kind': 'brake', 'time_s', 'speed_mps', 'decel_mps2'} | {'kind': 'leave_lane', 'trigger_s_m', 'accelerate_to_mps'}
    'queued_vehicle': None,  # None | {'extra_gap_m'}
    'wetness': 0.0, 'precipitation_deposits': 0.0, 'precipitation': 0.0, 'tire_friction': 3.5,
    'duration_s': 45.0,
}
# Every case differs from base in exactly one declared variable.
VARIANTS = {
    'base': {},
    'closer': {'initial_gap_m': 12.0, 'gap_hold_m': 12.0},
    'faster_ego': {'ego_set_speed_mps': 17.9, 'lead_speed_mps': 17.9},
    'slower_lead': {'lead_speed_mps': 9.0},
    'lead_brakes': {'lead_event': {'kind': 'brake', 'time_s': 12.0, 'speed_mps': 8.0, 'decel_mps2': 2.5}},
    'wet_surface': {'wetness': 80.0, 'precipitation_deposits': 80.0, 'precipitation': 60.0, 'tire_friction': 2.0},
    'following_ends': {'lead_event': {'kind': 'leave_lane', 'trigger_s_m': 250.0, 'accelerate_to_mps': 20.0}},
    'queued_traffic': {'queued_vehicle': {'extra_gap_m': 25.0}},
}
VARIABLE_OF = {'base': None, 'closer': 'initial_following_gap', 'faster_ego': 'common_travel_speed',
               'slower_lead': 'lead_speed', 'lead_brakes': 'lead_longitudinal_event',
               'wet_surface': 'surface_condition', 'following_ends': 'lead_lateral_event',
               'queued_traffic': 'traffic_ahead_of_lead'}


def case_params(name):
    if name not in VARIANTS:
        raise ValueError('Unknown case: ' + str(name))
    params = dict(BASE)
    params.update(VARIANTS[name])
    return params


def changed_from_base(name):
    base = case_params('base')
    return sorted(k for k, v in case_params(name).items() if v != base[k])


# ---------------------------------------------------------------- road geometry
def elevation_m(s):
    """Piecewise grade, parabolic crest. Mirrors the OpenDRIVE elevation records."""
    s0, s1 = CREST_S_M - CREST_VERTICAL_CURVE_M / 2, CREST_S_M + CREST_VERTICAL_CURVE_M / 2
    if s <= s0:
        return GRADE * s
    z0 = GRADE * s0
    if s <= s1:
        u = s - s0
        return z0 + GRADE * u - GRADE * u * u / CREST_VERTICAL_CURVE_M
    z1 = z0
    return z1 - GRADE * (s - s1)


def opendrive_xml():
    s0, s1 = CREST_S_M - CREST_VERTICAL_CURVE_M / 2, CREST_S_M + CREST_VERTICAL_CURVE_M / 2
    z0 = GRADE * s0
    z1 = z0
    curve = -GRADE / CREST_VERTICAL_CURVE_M
    lane = ''.join('<lane id="%d" type="driving" level="false"><width sOffset="0" a="%.2f" b="0" c="0" d="0"/>'
                   '<roadMark sOffset="0" type="solid" weight="standard" color="white" width="0.15"/></lane>' % (i, LANE_WIDTH_M)
                   for i in (-1, -2))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<OpenDRIVE><header revMajor="1" revMinor="4" name="hill_crest_following"'
            ' version="1" date="2026-11-08" north="0" south="0" east="0" west="0"/>'
            '<road name="hill_crest" length="%.1f" id="%d" junction="-1"><link/><planView>'
            '<geometry s="0" x="0" y="0" hdg="0" length="%.1f"><line/></geometry></planView>'
            '<elevationProfile><elevation s="0" a="0" b="%.4f" c="0" d="0"/>'
            '<elevation s="%.1f" a="%.4f" b="%.4f" c="%.8f" d="0"/>'
            '<elevation s="%.1f" a="%.4f" b="%.4f" c="0" d="0"/></elevationProfile>'
            '<lateralProfile/><lanes><laneSection s="0"><left/><center><lane id="0" type="none" level="false">'
            '<roadMark sOffset="0" type="solid" weight="standard" color="yellow" width="0.15"/></lane></center>'
            '<right>%s</right></laneSection></lanes></road></OpenDRIVE>\n'
            % (ROAD_LENGTH_M, ROAD_ID, ROAD_LENGTH_M, GRADE, s0, z0, GRADE, curve, s1, z1, -GRADE, lane))


def lane_center_offset_m(lane_id):
    """Signed OpenDRIVE t of a right-hand lane centre (negative to the right)."""
    return -(abs(lane_id) - 0.5) * LANE_WIDTH_M


def lane_id_at(t_m):
    """Lane id of a road-frame lateral offset t (OpenDRIVE sign), or None off the lanes."""
    if t_m > 0 or t_m < -2 * LANE_WIDTH_M:
        return None
    return -1 if t_m > -LANE_WIDTH_M else -2


def smoothstep(x):
    x = min(1.0, max(0.0, x))
    return x * x * x * (10 + x * (-15 + 6 * x))


def lateral_offset_m(t_since_start_s, from_lane=EGO_LANE, to_lane=DEST_LANE, duration_s=LANE_CHANGE_DURATION_S):
    a, b = lane_center_offset_m(from_lane), lane_center_offset_m(to_lane)
    return a + (b - a) * smoothstep(t_since_start_s / duration_s)


# ---------------------------------------------------------------- controllers
def lead_target_speed(params, t_s, lead_s=None):
    event = params['lead_event']
    v = params['lead_speed_mps']
    if event is None:
        return v
    if event['kind'] == 'brake':
        if t_s < event['time_s']:
            return v
        return max(event['speed_mps'], v - event['decel_mps2'] * (t_s - event['time_s']))
    if event['kind'] == 'leave_lane':
        if lead_s is not None and lead_s >= event['trigger_s_m']:
            return event['accelerate_to_mps']
        return v
    raise ValueError('Unknown lead event')


def ego_target_speed(params, gap_m, lead_speed_mps):
    """Set speed, limited by a hold on the authored bumper gap when a lead is in lane.

    The authored gap is an engineering setpoint chosen from the case table; it is
    never a judgment of what is reasonable and prudent.
    """
    v = params['ego_set_speed_mps']
    if gap_m is None:
        return v
    return max(0.0, min(v, lead_speed_mps + 0.5 * (gap_m - params['gap_hold_m'])))


class SpeedPI:
    """Throttle/brake in [0,1] from a speed error. Deterministic, no wall clock."""
    def __init__(self, kp=0.35, ki=0.05, limit=0.5):
        self.kp, self.ki, self.limit, self.integral = kp, ki, limit, 0.0

    def step(self, target, speed, dt=DT):
        error = target - speed
        self.integral = max(-self.limit / max(self.ki, 1e-9), min(self.limit / max(self.ki, 1e-9), self.integral + error * dt))
        u = self.kp * error + self.ki * self.integral
        u = max(-1.0, min(1.0, u))
        return (u, 0.0) if u >= 0 else (0.0, -u)


def steer_command(lateral_error_m, heading_error_rad, speed_mps, k_lat=0.9, k_head=1.2):
    """Stanley-style steer in [-1,1]; sign follows the supplied error convention."""
    v = max(speed_mps, 1.0)
    angle = k_head * heading_error_rad + math.atan2(k_lat * lateral_error_m, v)
    return max(-1.0, min(1.0, angle / 0.6))


# ---------------------------------------------------------------- kinematic preview
def preview(name, duration_s=None):
    """Software-only kinematic rollout used by CPU tests and synthetic fixtures.

    It follows the same target-speed and lateral-profile functions as the runner,
    but it is NOT evidence of CARLA physics, camera visibility or completion.
    """
    p = case_params(name)
    duration = duration_s or p['duration_s']
    n = int(round(duration * RATE_HZ))
    L = VEHICLE_LENGTH_M
    ego_s, ego_v = EGO_S0_M, p['ego_set_speed_mps']
    lead_s, lead_v = EGO_S0_M + L + p['initial_gap_m'], p['lead_speed_mps']
    queue_s = None if not p['queued_vehicle'] else lead_s + L + p['queued_vehicle']['extra_gap_m']
    ego_t, lead_t, lc_start, lead_lane_t0 = lateral_offset_m(0), lateral_offset_m(0), None, None
    rows = []
    for i in range(n):
        t = i * DT
        lead_in_lane = lane_id_at(lead_t) is not None and lane_id_at(lead_t) == lane_id_at(ego_t)
        gap = (lead_s - ego_s - L) if (lead_in_lane and lead_s > ego_s) else None
        if lc_start is None and ego_s >= LANE_CHANGE_TRIGGER_S_M:
            lc_start = t
        ego_t = lateral_offset_m(t - lc_start) if lc_start is not None else lateral_offset_m(0)
        if params_leave(p) and lead_lane_t0 is None and lead_s >= p['lead_event']['trigger_s_m']:
            lead_lane_t0 = t
        lead_t = lateral_offset_m(t - lead_lane_t0) if lead_lane_t0 is not None else lateral_offset_m(0)
        rows.append({'frame': 1000 + i, 'time_s': round(t, 6), 'ego_s_m': ego_s, 'ego_t_m': ego_t, 'ego_speed_mps': ego_v,
                     'lead_s_m': lead_s, 'lead_t_m': lead_t, 'lead_speed_mps': lead_v, 'bumper_gap_m': gap,
                     'queued_s_m': queue_s, 'ego_lane_id': lane_id_at(ego_t), 'lead_lane_id': lane_id_at(lead_t)})
        target = ego_target_speed(p, gap, lead_v)
        ego_v += max(-4.0, min(2.0, (target - ego_v) * 1.0)) * DT
        lead_v += max(-4.0, min(2.0, (lead_target_speed(p, t, lead_s) - lead_v) * 2.0)) * DT
        ego_s += ego_v * DT
        lead_s += lead_v * DT
        if queue_s is not None:
            queue_s += p['lead_speed_mps'] * DT
    return rows


def params_leave(p):
    return bool(p['lead_event']) and p['lead_event']['kind'] == 'leave_lane'
