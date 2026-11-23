"""Experimental bicycle encounter controller; engineering cues only."""
from __future__ import annotations
import math
from bicycle_encounter import MODES, SourceError, require, verify_site

def command(site, root, mode, ego_xy, rider_xy, rider_speed_mps, elapsed_s):
    """Return target velocity and route waypoint from source-verified geometry.

    Maintains a waiting point while the cyclist approaches or occupies the route
    crossing. The other mode commands continued travel through the crossing.
    Neither command establishes statutory intent or lawful riding.
    """
    require(mode in MODES, 'unknown encounter mode')
    crossing=verify_site(site,root)[0]
    require(all(math.isfinite(float(x)) for x in (*ego_xy,*rider_xy,rider_speed_mps,elapsed_s)), 'nonfinite controller input')
    require(rider_speed_mps>=0 and elapsed_s>=0, 'invalid speed/time')
    rider_distance=math.dist(rider_xy,crossing)
    ego_distance=math.dist(ego_xy,crossing)
    # This is an engineering switch, not a legal conflict or interference cutoff.
    proximity=site['control_proximity_m']
    require(0<proximity<30, 'control proximity outside physical planning envelope')
    waiting=mode=='maintain_clearance' and rider_distance<=proximity and ego_distance<=proximity and rider_speed_mps>0
    return {'target_speed_mps':0.0 if waiting else float(site['ego_travel_speed_mps']),
            'next_waypoint_xy':site['ego_route_xy'][-1],
            'waiting_for_rider':waiting,
            'mode_command':mode,
            'engineering_proximity_m':proximity,
            'legal_verdict':None}
