"""Descriptive original-source parking geometry and pedestrian history measurement."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from parking_source import load_site, sha, point


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def verified(attempt,name,acquisition):
    path=Path(attempt)/name
    if not path.is_file():
        raise ValueError('Missing required source: '+name)
    ref=acquisition.get(name,{})
    if ref.get('kind')!='original_native' or ref.get('sha256')!=sha(path):
        raise ValueError('missing or stale original Native source: '+name)
    return path


def measure(attempt):
    attempt=Path(attempt)
    cfg=json.loads((attempt/'config.json').read_text())
    if cfg.get('assignment_id')!='testing__C150078__LVMC-11-40-170__cycle_or_scooter_operator':
        raise ValueError('wrong exact assignment')
    acquisition=json.loads((attempt/'acquisition.json').read_text())
    names=('reviewed-site/site.json','parking-events.jsonl','pedestrian-tracks.jsonl','video_frames.jsonl','trace.jsonl')
    paths={name:verified(attempt,name,acquisition) for name in names}
    site,records=load_site(paths['reviewed-site/site.json'],cfg['selected_case_id'])
    for ref in site['sources'].values():
        verified(attempt,'reviewed-site/'+ref['path'],acquisition)
    events=rows(paths['parking-events.jsonl'])
    tracks=rows(paths['pedestrian-tracks.jsonl'])
    frames=rows(paths['video_frames.jsonl'])
    trace=rows(paths['trace.jsonl'])
    if not events or len(events)!=len(tracks) or len(events)!=len(frames) or len(events)!=len(trace):
        raise ValueError('original parking, pedestrian, video and trace frames differ')
    fixture=(attempt/'fixture-provenance.json').is_file()
    if len(events)<200 and not fixture:
        raise ValueError('original parking and pedestrian window incomplete')
    distances=[]
    parked=[]
    observed_relations=[]
    person_id=records['person']['responsible_person_identity']
    device_id=records['device']['physical_identity']
    for e,p,v,t in zip(events,tracks,frames,trace):
        identity=(e.get('frame'),e.get('time_s'))
        if any((r.get('frame'),r.get('time_s'))!=identity for r in (p,t)) or (v.get('carla_frame'),v.get('time_s'))!=identity:
            raise ValueError('original frame/time join mismatch')
        if e.get('person_id')!=person_id or e.get('device_id')!=device_id:
            raise ValueError('original parking actor identity mismatch')
        if type(e.get('parked')) is not bool:
            raise ValueError('observed parking state required')
        parked.append(e['parked'])
        if e.get('placement_relation') not in ('sidewalk_rack','sidewalk_building','sidewalk_curb','roadway_curb','other_street_location'):
            raise ValueError('original observed placement relation missing')
        if e['parked'] and e['placement_relation']!=site['requested']['placement']:
            raise ValueError('original observed placement differs from exact case')
        if e['parked'] and site['requested']['placement']=='sidewalk_rack' and e.get('rack_support_contact') is not True:
            raise ValueError('original rack support contact absent')
        observed_relations.append(e['placement_relation'])
        point(e.get('device_xy'))
        passing=p.get('pedestrian_xy')
        if passing is not None:
            distances.append(math.dist(point(passing),point(e['device_xy'])))
        if p.get('passage_status') not in ('passing','waiting','turning','absent'):
            raise ValueError('original pedestrian passage state missing')
    if not any(parked):
        raise ValueError('original parking episode absent')
    if not distances:
        raise ValueError('original pedestrian passage history absent')
    return {'case_id':cfg['selected_case_id'],'device_class':records['device']['covered_class'],
            'observed_placement':site['requested']['placement'],'observed_placement_history':observed_relations,'parked_frame_count':sum(parked),
            'observed_pedestrian_device_min_distance_m':min(distances),
            'pedestrian_passage_states':[p['passage_status'] for p in tracks],
            'available_route_count':len(records['pedestrian_context']['available_passing_routes']),
            'sources':{name:acquisition[name]['sha256'] for name in names},
            'legal_least_obstruction':'unresolved','diagnostic_fixture':fixture,
            'physical_acceptance':'unreviewed'}
