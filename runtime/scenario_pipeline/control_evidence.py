"""Observed sign passage, distinct from declared longitudinal applicability."""
import json
import math
from pathlib import Path


def passage_bracket(trace, position, corridor_m):
    """Bracket center passage of a roadside sign using local travel direction."""
    for i, (a, b) in enumerate(zip(trace, trace[1:])):
        p = [a['position']['x'], a['position']['y']]
        q = [b['position']['x'], b['position']['y']]
        delta = [q[j] - p[j] for j in range(2)]
        length = math.hypot(*delta)
        if length <= 1e-8:
            continue
        direction = [v / length for v in delta]
        along = sum((position[j] - p[j]) * direction[j] for j in range(2))
        lateral = abs((position[0]-p[0])*direction[1]-(position[1]-p[1])*direction[0])
        if 0 <= along < length and lateral <= corridor_m:
            return {'sample_indices': [i, i+1], 'time_bracket_s': [a['time_s'], b['time_s']],
                    'lateral_distance_m': lateral,
                    'method': 'Recorded vehicle center crossing the sign station in local trajectory direction; not a governance inference'}
    raise ValueError('Recorded approach and passage of the selected speed sign are missing')


def posted_sign_evidence(attempt, trace, scope, limit_mps):
    from trace_scope_audit import scenes
    from shapely.geometry import LineString, Polygon
    attempt = Path(attempt)
    config = json.loads((attempt/'config.json').read_text())
    observations = [json.loads(line) for line in (attempt/'speed_limit_sign_evidence.jsonl').read_text().splitlines()]
    if len(observations) != len(trace) or any(abs(a['time_s']-b['time_s']) > 1e-6 for a,b in zip(observations,trace)):
        raise ValueError('Native speed-sign observations do not cover the full recording')
    selected = observations[0]['value']['resolved_sign']
    point = selected['transform']['position_m']
    position = [point['x'], point['y']]
    lane = selected['lane_association']
    for row in observations:
        observed = row['value']['resolved_sign']
        if observed != selected:
            raise ValueError('Selected native speed sign changed during recording')
    if selected['posted_unit'] != 'km/h' or abs(selected['posted_value']/3.6-limit_mps) > 1e-6:
        raise ValueError('Native posted value/units disagree with the selected limit')
    if any(lane[k] != config['zone'][k] for k in ('road_id','section_id','lane_id')):
        raise ValueError('Native speed sign belongs to a different lane')
    tolerance = config['measurements']['sign_position_tolerance_m']
    if math.dist(position, config['sign']['position_m'][:2]) > tolerance:
        raise ValueError('Recorded native sign does not match the selected physical sign')
    iterator = scenes(attempt/'traffic_spec/trace.json')
    try:
        scene = next(iterator)
    finally:
        iterator.close()
    signs = [d for d in scene['devices'] if d['kind']=='speed_limit_sign' and d.get('governs')
             and abs(d.get('speed_value',-1)-limit_mps)<1e-6
             and math.dist(d['position'],[position[0],-position[1]])<=tolerance]
    if len(signs) != 1:
        raise ValueError('Delivered trace lacks the selected native sign and governed portion')
    passage = passage_bracket(trace, position, lane.get('lane_width_m',4)+tolerance)
    portions = [p for p in scope.get('authored_speed_control_applicability',[])
                if p['governed_region'] in signs[0]['governs'] and abs(p['speed_mps']-limit_mps)<1e-6]
    flags = [any(p['applicable_frames'][i] for p in portions) for i in range(len(trace))]
    if not portions or flags[0] or not any(flags[passage['sample_indices'][1]:]):
        raise ValueError('Governed-portion evidence must include entry and observations after physical sign passage')
    subject = next(u for u in scene['users'] if u['track']==scene['subject'])
    radius = math.hypot(*subject['kin']['extent'][:2])
    route = LineString([(r['position']['x'],-r['position']['y']) for r in trace]).buffer(radius)
    governed = {rid for d in scene['devices'] if d['kind']=='traffic_signal' for rid in d.get('governs',[])}
    regions = [Polygon(s['boundary']) for s in scene['structures'] if s['id'] in governed]
    if any(route.intersects(region) for region in regions):
        raise ValueError('Posted-speed route may overlap an unrelated signal-controlled region')
    return {'native_sign_actor_id': selected['actor_id'], 'delivered_sign_id': signs[0]['id'],
            'posted_value': selected['posted_value'], 'posted_unit': 'km/h', 'passage': passage,
            'governed_portion_after_passage_observed': True, 'no_signal_region_overlap': True,
            'governance_provenance': config['zone'].get('provenance'),
            'scope': 'Native sign and measured passage; road-portion governance remains explicitly authored'}
