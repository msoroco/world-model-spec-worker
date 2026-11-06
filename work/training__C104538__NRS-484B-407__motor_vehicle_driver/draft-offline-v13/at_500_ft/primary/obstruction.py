"""Candidate-specific physical barrier placements for the authored inner curve."""
from __future__ import annotations

import math
from engineering import plan
from geometry import RADIUS_M, TURN_STATION_M, road_height


def placements(suffix: str, candidate: str) -> list[dict]:
    construction = plan(suffix, candidate)
    radius = construction['authored_obstruction_radius_m']
    step = construction['knobs']['obstruction_segment_length_m']
    # Cover every center-reference ray to 550 ft in either direction, with an
    # extra 12 m on each side. Actor dimensions and opacity require Native audit.
    half_length = 550 * .3048 + 12
    count = math.ceil(2 * half_length / step)
    result=[]
    for index in range(count+1):
        arc_m = -half_length + index * (2 * half_length / count)
        angle = arc_m / RADIUS_M
        station = TURN_STATION_M + arc_m
        result.append({'index':index,'station_m':station,
                       'native_xyz_m':[radius*math.cos(angle),
                                       -radius*math.sin(angle),
                                       road_height(station)+.5],
                       'native_tangent_yaw_deg':math.degrees(-angle-math.pi/2),
                       'requested_inner_radius_m':radius,
                       'authored_segment_step_m':2*half_length/count})
    return result


def check() -> dict:
    summaries={}
    for suffix in ('below_500_ft','at_500_ft','above_500_ft'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            rows=placements(suffix,candidate)
            assert len(rows)>150
            steps=[math.dist(a['native_xyz_m'][:2],b['native_xyz_m'][:2])
                   for a,b in zip(rows,rows[1:])]
            assert max(steps)<=plan(suffix,candidate)['knobs']['obstruction_segment_length_m']+1e-6
            assert all(math.isclose(math.hypot(*row['native_xyz_m'][:2]),
                                    row['requested_inner_radius_m'],abs_tol=1e-8)
                       for row in rows)
            summaries[suffix+'__'+candidate]={'actors_planned':len(rows),
                                             'maximum_center_gap_m':max(steps)}
    return {'passed':True,'candidate_layouts':12,'layouts':summaries,
            'native_actor_spawned':False,'physical_opacity_verified':False}
