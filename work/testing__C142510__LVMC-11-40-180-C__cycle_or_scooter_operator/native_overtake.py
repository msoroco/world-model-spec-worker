"""Lazy Native construction for a physically reviewed connected sidewalk.

The adapter must provide a real audible emitter and pedestrian microphone;
state flags or a sound-command log cannot replace original waveform capture.
"""
from __future__ import annotations

import hashlib
import math


def need(ok,message):
    if not ok:raise ValueError(message)


def build(adapter,site):
    """Spawn rider/pedestrian and audio devices, with owned-resource rollback."""
    need(site.get('cell_id')=='C142510' and
         site.get('physical_surface_kind')=='sidewalk' and
         site.get('sidewalk_connected') is True,
         'reviewed connected physical sidewalk required')
    need(site.get('rider_kind') in ('bicycle','electric_bicycle','electric_scooter'),
         'covered rider kind missing')
    road=adapter.map_opendrive_bytes()
    need(isinstance(road,bytes) and hashlib.sha256(road).hexdigest()==site.get('map_sha256'),
         'live map differs from reviewed sidewalk source')
    for key in ('sidewalk_source_citation','connected_route_citation',
                'rider_blueprint_sha256','pedestrian_blueprint_sha256',
                'audible_emitter_source_sha256','microphone_source_sha256'):
        need(bool(site.get(key)),key+' missing')
    route=site.get('rider_route_xyz_m');walk=site.get('pedestrian_route_xyz_m')
    for name,points in (('rider',route),('pedestrian',walk)):
        need(isinstance(points,list) and len(points)>=2 and
             all(isinstance(p,list) and len(p)==3 and
                 all(type(v) in (int,float) and math.isfinite(v) for v in p)
                 for p in points),name+' reviewed 3D route missing')
        need(math.dist(points[0],points[-1])>2,name+' route has no progress')
    need(adapter.sidewalk_route_readback(route,site['sidewalk_id']) is True and
         adapter.sidewalk_route_readback(walk,site['sidewalk_id']) is True,
         'live route not on same physical sidewalk')
    owned=[]
    try:
        rider=adapter.spawn_rider(site['rider_kind'],route[0],
                                  blueprint_sha256=site['rider_blueprint_sha256'])
        need(rider is not None,'covered rider spawn failed')
        owned.append(rider)
        pedestrian=adapter.spawn_pedestrian(walk[0],
                                            blueprint_sha256=site['pedestrian_blueprint_sha256'])
        need(pedestrian is not None,'pedestrian spawn failed')
        owned.append(pedestrian)
        emitter=adapter.attach_audible_emitter(rider,
            source_sha256=site['audible_emitter_source_sha256'])
        need(emitter is not None and adapter.read_emitter(emitter).get('physically_present') is True,
             'real audible emitter readback missing')
        owned.append(emitter)
        microphone=adapter.attach_pedestrian_microphone(pedestrian,
            source_sha256=site['microphone_source_sha256'])
        need(microphone is not None and
             adapter.read_microphone(microphone).get('recording_enabled') is True,
             'pedestrian microphone readback missing')
        owned.append(microphone)
        adapter.set_rider_route(rider,route)
        adapter.set_pedestrian_route(pedestrian,walk)
        return {'rider':rider,'pedestrian':pedestrian,'emitter':emitter,
                'microphone':microphone,'owned':tuple(owned)}
    except Exception:
        for resource in reversed(owned):adapter.destroy(resource)
        raise


def request_signal(adapter,emitter,original_frame,case_signal_frame):
    """Request an audible signal on a declared frame; measure WAV independently."""
    need(type(original_frame) is int and type(case_signal_frame) is int,
         'original signal frame schedule missing')
    if original_frame==case_signal_frame:
        adapter.emit_audible_signal(emitter)
        return True
    return False
