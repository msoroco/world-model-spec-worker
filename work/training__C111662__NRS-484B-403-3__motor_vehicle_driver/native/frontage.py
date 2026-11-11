"""Authored roadside business frontage request and measured Native extent.

The 300/600 foot probe comes from the frozen conditional witness. An authored
business use and a spawned mesh never establish a statutory district by themselves.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

FEET_PER_METRE = 3.280839895013123
WINDOW_FT = 600.0
MIN_FRONTAGE_FT = 300.0
WINDOW_M = WINDOW_FT / FEET_PER_METRE
MIN_FRONTAGE_M = MIN_FRONTAGE_FT / FEET_PER_METRE
WINDOW_X_M = (-WINDOW_M / 2, WINDOW_M / 2)
# Leave the crossing at x=0 open. Both comparison locations are within the
# same 600-foot window and see exactly the same authored frontage.
SEGMENTS = ((-75.0, -25.0), (25.0, 75.0))
FRONTAGE_Y_M = 22.0
SPACING_M = 5.0
ASSET_TERMS = ('building', 'shop', 'store', 'cafe')


def union_length(intervals):
    total = 0.0
    end = -math.inf
    for lo, hi in sorted(intervals):
        if not all(math.isfinite(v) for v in (lo, hi)) or hi <= lo:
            raise ValueError('Invalid frontage interval')
        total += max(0.0, hi - max(lo, end))
        end = max(end, hi)
    return total


def clipped_frontage(intervals, window=WINDOW_X_M):
    lo, hi = window
    if not all(math.isfinite(v) for v in window) or hi <= lo or hi-lo > WINDOW_M+1e-9:
        raise ValueError('Frontage window exceeds 600 feet')
    clipped = [(max(a, lo), min(b, hi)) for a, b in intervals if min(b, hi)>max(a, lo)]
    return union_length(clipped)


def authored_plan():
    length = clipped_frontage(SEGMENTS)
    if length < MIN_FRONTAGE_M:
        raise ValueError('Authored business frontage below 300 feet')
    stations = []
    for start, stop in SEGMENTS:
        count = round((stop-start)/SPACING_M)
        if count*SPACING_M != stop-start:
            raise ValueError('Frontage spacing does not tile segment')
        stations.extend(round(start+SPACING_M*(i+.5),6) for i in range(count))
    return {'format':'c111662-authored-frontage-plan-v1',
            'source':'inputs/training__C111662__NRS-484B-403-3__motor_vehicle_driver/witnesses.json',
            'source_rule':'conditional witness: business or industrial building-use frontage of at least 300 feet within a 600-foot highway interval',
            'window_x_m':list(WINDOW_X_M),'segments_x_m':[list(s) for s in SEGMENTS],
            'station_x_m':stations,'frontage_y_m':FRONTAGE_Y_M,
            'authored_frontage_m':length,'authored_frontage_ft':length*FEET_PER_METRE,
            'minimum_frontage_ft':MIN_FRONTAGE_FT,'maximum_window_ft':WINDOW_FT,
            'authored_building_use':'business','district_designation_verified':False,
            'native_building_use_verified':False,'legal_verdict':None}


def choose_blueprint(library):
    matches = [bp for bp in library.filter('static.prop.*')
               if any(term in bp.id.lower() for term in ASSET_TERMS)]
    if not matches:
        raise RuntimeError('No building/shop/store/cafe static prop blueprint for authored frontage')
    return sorted(matches,key=lambda item:item.id)[0]


def spawn_and_measure(world, carla, plan, owned):
    """Place actual props and reject Native geometry short of the authored probe."""
    if plan != authored_plan():
        raise ValueError('Frontage plan changed')
    blueprint = choose_blueprint(world.get_blueprint_library())
    intervals = []
    actors = []
    for x in plan['station_x_m']:
        actor = world.try_spawn_actor(blueprint,
            carla.Transform(carla.Location(x=x,y=plan['frontage_y_m'],z=0.0),
                            carla.Rotation(yaw=0)))
        if actor is None:
            raise RuntimeError('Frontage prop failed to spawn at x='+str(x))
        owned.append(actor)
        actors.append(actor)
        transform = actor.get_transform()
        verts = actor.bounding_box.get_world_vertices(transform)
        if not verts:
            raise RuntimeError('Frontage prop has no Native bounding vertices')
        intervals.append((min(v.x for v in verts),max(v.x for v in verts)))
    # Count only geometry in the two authored segments, never the crossing gap.
    measured = sum(clipped_frontage(intervals,segment) for segment in SEGMENTS)
    if measured+1e-9 < MIN_FRONTAGE_M:
        raise RuntimeError('Spawned building frontage below 300 feet: '+str(measured*FEET_PER_METRE))
    return {'format':'c111662-native-frontage-readback-v1',
            'source_kind':'original_native_geometry',
            'blueprint_id':blueprint.id,'actor_ids':[a.id for a in actors],
            'authored_segments_x_m':plan['segments_x_m'],
            'native_actor_intervals_x_m':[[a,b] for a,b in intervals],
            'native_frontage_m':measured,'native_frontage_ft':measured*FEET_PER_METRE,
            'district_designation_verified':False,'building_use_legally_verified':False,
            'legal_verdict':None}


def write_plan(path):
    Path(path).write_text(json.dumps(authored_plan(),indent=2)+'\n')


if __name__=='__main__':
    write_plan(Path(__file__).with_name('frontage-plan.json'))
