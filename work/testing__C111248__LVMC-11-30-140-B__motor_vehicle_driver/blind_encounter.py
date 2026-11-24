"""Source-bound Native encounter planner and saved-history measurements.

No CARLA import occurs at module import. This module does not decide legal compliance.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Mapping, Sequence


@dataclass(frozen=True)
class EncounterCase:
    case_id: str
    cue: str
    encounter: str
    response: str
    precaution: str


CASES = (
    EncounterCase('white_full_stop_wait', 'white_cane', 'approach', 'full_stop', 'wait_until_clear'),
    EncounterCase('white_roll_through', 'white_cane', 'approach', 'rolling', 'wait_until_clear'),
    EncounterCase('white_early_proceed', 'white_cane', 'approach', 'full_stop', 'early_proceed'),
    EncounterCase('white_contact_stop', 'white_cane', 'contact', 'full_stop', 'wait_until_clear'),
    EncounterCase('red_tip_full_stop_wait', 'red_tip_cane', 'approach', 'full_stop', 'wait_until_clear'),
    EncounterCase('assisted_full_stop_wait', 'assisted_person', 'approach', 'full_stop', 'wait_until_clear'),
)
CASE_BY_ID = {case.case_id: case for case in CASES}


def plan_native(case_id: str, *, map_id: str, route_waypoints: Sequence[Mapping],
                pedestrian_pose: Mapping, blindness_attestation: Mapping,
                cue_source: Mapping, driver_actor_id: int, pedestrian_actor_id: int) -> dict:
    """Require independently sourced context before a Native spawn/controller plan.

    The attestation is a source reference, not a simulator assertion of blindness.
    Waypoints and pedestrian pose must be read from the chosen Native map.
    """
    case = CASE_BY_ID[case_id]
    if not map_id or not route_waypoints or len(route_waypoints) < 2:
        raise ValueError('source-bound map and approach route required')
    if any(w.get('map_id') != map_id or not all(k in w for k in ('x', 'y', 'lane_id', 'road_id')) for w in route_waypoints):
        raise ValueError('route waypoints must identify the chosen map, road, lane and pose')
    if pedestrian_pose.get('map_id') != map_id or not all(k in pedestrian_pose for k in ('x', 'y', 'ground_z')):
        raise ValueError('source-bound pedestrian pose required')
    if blindness_attestation.get('person_actor_id') != pedestrian_actor_id or not blindness_attestation.get('source_sha256'):
        raise ValueError('independent blindness attestation required')
    if cue_source.get('person_actor_id') != pedestrian_actor_id or cue_source.get('cue') != case.cue or not cue_source.get('source_sha256'):
        raise ValueError('observed cane or assistant source required')
    if driver_actor_id <= 0 or pedestrian_actor_id <= 0 or driver_actor_id == pedestrian_actor_id:
        raise ValueError('distinct source-bound actor ids required')
    p = pedestrian_pose
    nearest = min(hypot(w['x']-p['x'], w['y']-p['y']) for w in route_waypoints)
    if nearest > 12:
        raise ValueError('route does not approach the protected pedestrian')
    if case.encounter == 'contact':
        # Contact is observed only in a later saved trace; do not command a collision.
        controller = 'brake_on_person_approach'
    elif case.response == 'rolling':
        controller = 'bounded_creep_and_brake_on_conflict'
    else:
        controller = 'brake_on_person_approach'
    return {
        'case_id': case_id, 'map_id': map_id, 'route_waypoints': list(route_waypoints),
        'pedestrian_pose': dict(p), 'driver_actor_id': driver_actor_id,
        'pedestrian_actor_id': pedestrian_actor_id,
        'blindness_attestation': dict(blindness_attestation), 'cue_source': dict(cue_source),
        'controller': controller, 'precaution_policy': case.precaution,
        'comparison_knob': {'response': case.response, 'encounter': case.encounter, 'cue': case.cue},
        'capture': {'hz': 20, 'duration_s': 45, 'original_history': True,
                    'required_cameras': ['front', 'left', 'right', 'rear']},
    }


def measure_saved(case_id: str, rows: Sequence[Mapping], *, attestation: Mapping, cue_source: Mapping) -> dict:
    """Measure events from uninterrupted original 20 Hz rows; never infer blindness."""
    case = CASE_BY_ID[case_id]
    if not rows:
        raise ValueError('missing original history')
    if not attestation.get('source_sha256') or not cue_source.get('source_sha256') or cue_source.get('cue') != case.cue:
        raise ValueError('missing independent blindness/cue sources')
    actor = attestation.get('person_actor_id')
    if actor is None or actor != cue_source.get('person_actor_id'):
        raise ValueError('person identity source mismatch')
    frames = [r.get('frame') for r in rows]
    if not all(isinstance(f, int) for f in frames) or frames != list(range(frames[0], frames[0]+len(frames))):
        raise ValueError('nonconsecutive original frames')
    times = [r.get('time_s') for r in rows]
    if not all(isinstance(t, (int,float)) and isfinite(t) for t in times) or any(abs((b-a)-0.05)>0.002 for a,b in zip(times,times[1:])):
        raise ValueError('original 20 Hz time join failed')
    for r in rows:
        if r.get('person_actor_id') != actor or not all(k in r for k in ('driver_speed_mps','body_gap_m','person_in_path','person_clear','contact','precaution')):
            raise ValueError('missing person or required original measurement')
        if not all(isinstance(r[k], (int,float)) and isfinite(r[k]) for k in ('driver_speed_mps','body_gap_m')):
            raise ValueError('nonfinite speed or gap')
    approach = [i for i,r in enumerate(rows) if r['person_in_path'] and r['body_gap_m'] >= 0]
    if not approach:
        raise ValueError('no measured approach')
    first = approach[0]
    stops = [i for i in range(first,len(rows)) if rows[i]['driver_speed_mps'] <= 0.05]
    stop = stops[0] if stops else None
    proceed = next((i for i in range((stop+1 if stop is not None else first+1),len(rows)) if rows[i]['driver_speed_mps'] > 0.2), None)
    return {
        'case_id': case_id, 'person_actor_id': actor, 'first_approach_frame': frames[first],
        'first_stop_frame': frames[stop] if stop is not None else None,
        'first_proceed_frame': frames[proceed] if proceed is not None else None,
        'first_contact_frame': next((frames[i] for i,r in enumerate(rows) if r['contact']), None),
        'gap_at_approach_m': rows[first]['body_gap_m'],
        'gap_at_stop_m': rows[stop]['body_gap_m'] if stop is not None else None,
        'person_clear_at_proceed': rows[proceed]['person_clear'] if proceed is not None else None,
        'precaution_at_proceed': rows[proceed]['precaution'] if proceed is not None else None,
        'attestation_sha256': attestation['source_sha256'], 'cue_sha256': cue_source['source_sha256'],
        'history_start_frame': frames[0], 'history_end_frame': frames[-1],
        'source_sample_count': len(rows),
        'interpretation_pending': ['immediately', 'necessary precautions', 'avoid accident or injury'],
    }


def audit_comparison(left: Mapping, right: Mapping, *, deliberate: str) -> dict:
    """Reject missing evidence and unexpected changes in paired saved results."""
    required = ('case_id','person_actor_id','attestation_sha256','history_start_frame','history_end_frame','source_sample_count')
    if any(k not in x for x in (left,right) for k in required):
        raise ValueError('missing comparison evidence')
    if deliberate not in ('response','precaution','cue','encounter'):
        raise ValueError('undeclared comparison variable')
    fixed = ('person_actor_id','attestation_sha256','source_sample_count')
    if any(left[k] != right[k] for k in fixed):
        raise ValueError('fixed identity or capture condition changed')
    lc, rc = CASE_BY_ID[left['case_id']], CASE_BY_ID[right['case_id']]
    for name in ('cue','encounter','response','precaution'):
        if name != deliberate and getattr(lc,name) != getattr(rc,name):
            raise ValueError('undeclared case condition changed')
    if getattr(lc,deliberate) == getattr(rc,deliberate):
        raise ValueError('comparison variable did not change')
    return {'left':left['case_id'],'right':right['case_id'],'deliberate':deliberate,'fixed_checks':list(fixed),'passed':True}


def construct_native(adapter, plan: Mapping) -> dict:
    """Create/identify the route actors and visible cue through a local Native adapter.

    Adapter methods are map_waypoint, spawn_vehicle, spawn_pedestrian,
    attach_cue, actor_readback and destroy_actor. This is lazy and testable
    without CARLA. On any failed readback, owned actors are destroyed.
    """
    case = CASE_BY_ID[plan['case_id']]
    owned = []
    try:
        map_id = plan['map_id']
        for waypoint in plan['route_waypoints']:
            native_wp = adapter.map_waypoint(map_id, waypoint['road_id'], waypoint['lane_id'], waypoint['x'], waypoint['y'])
            if native_wp is None:
                raise ValueError('Native route waypoint unavailable')
        vehicle = adapter.spawn_vehicle(plan['route_waypoints'][0])
        owned.append(vehicle)
        person = adapter.spawn_pedestrian(plan['pedestrian_pose'])
        owned.append(person)
        cue = adapter.attach_cue(person, case.cue)
        owned.append(cue)
        readback = {name: adapter.actor_readback(actor) for name, actor in [('vehicle',vehicle),('person',person),('cue',cue)]}
        if not all(r.get('alive') for r in readback.values()):
            raise ValueError('Native actor readback failed')
        if readback['cue'].get('cue') != case.cue or readback['cue'].get('attached_to') != readback['person'].get('actor_id'):
            raise ValueError('Native cue attachment readback failed')
        if readback['person'].get('actor_id') == readback['vehicle'].get('actor_id'):
            raise ValueError('Native participant identity collision')
        if (readback['vehicle'].get('actor_id') != plan['driver_actor_id'] or
                readback['person'].get('actor_id') != plan['pedestrian_actor_id']):
            raise ValueError('Native participant identity differs from reviewed map source')
        return {'map_id':map_id,'actors':readback,'controller':plan['controller'],
                'precaution_policy':plan['precaution_policy'],
                'owned_handles': tuple(owned),
                'source_note':'Actor readback does not prove blindness; independent attestation remains required.'}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy_actor(actor)
        raise
