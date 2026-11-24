"""Independent C125714 original-source controller comparison, no legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from entry_timing import intersects, polygon

BASE='testing__C125714__NRS-484B-250-2__motor_vehicle_driver'
CASES=(BASE+'__yield_wait_for_other_clear',BASE+'__advance_at_release')
SOURCES=('road.xodr','site-context.json','controller-history.jsonl',
         'other-body-history.jsonl','video_frames.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def one(attempt,case):
    attempt=Path(attempt)
    provenance=read(attempt/'acquisition-provenance.json')
    diagnostic=provenance.get('diagnostic_fixture') is True
    if provenance.get('provenance_kind') != ('synthetic_fixture' if diagnostic else 'native'):
        raise ValueError('original acquisition provenance differs')
    manifest=read(attempt/('original-bindings.json' if diagnostic else 'source-manifest.json'))
    kind='diagnostic_fixture' if diagnostic else 'original_native'
    for name in SOURCES:
        if (not (attempt/name).is_file() or (attempt/name).is_symlink() or
                manifest.get(name,{}).get('kind')!=kind or
                manifest[name].get('sha256')!=sha(attempt/name)):
            raise ValueError('source-bound original missing or changed: '+name)
    site=read(attempt/'site-context.json')
    if site.get('case_id')!=case or site.get('map_sha256')!=sha(attempt/'road.xodr'):
        raise ValueError('exact original site/map differs')
    controls,bodies,mapping=(rows(attempt/name) for name in
                             ('controller-history.jsonl','other-body-history.jsonl',
                              'video_frames.jsonl'))
    if not controls or len(controls)!=len(bodies) or len(bodies)!=len(mapping):
        raise ValueError('complete original controller/actor/frame history required')
    region=polygon(site['intersection_polygon_xy_m'])
    inside=[];policy=None
    for i,(control,body,frame) in enumerate(zip(controls,bodies,mapping)):
        if (frame.get('video_frame')!=i or
                (control.get('frame'),control.get('time_s'))!=
                (body.get('frame'),body.get('time_s')) or
                (body.get('frame'),body.get('time_s'))!=
                (frame.get('carla_frame'),frame.get('time_s')) or
                body.get('actor_id')!=site['other_actor_id']):
            raise ValueError('original controller/actor/frame join differs')
        current=control.get('control_policy')
        if policy is None:policy=current
        if current!=policy:
            raise ValueError('controller policy changed during original run')
        if intersects(polygon(body['body_vertices_xy_m']),region):
            brake=control.get('ego_brake')
            if type(brake) not in (int,float) or not 0<=brake<=1:
                raise ValueError('original ego brake sample missing')
            inside.append(brake)
    if not inside:
        raise ValueError('other vehicle never occupied reviewed crossing')
    return {'case_id':case,'policy':policy,'other_inside_frames':len(inside),
            'ego_brake_all_other_inside':all(v>=.9 for v in inside),
            'ego_released_while_other_inside':any(v<.1 for v in inside),
            'diagnostic_fixture':diagnostic,
            'site':site,'sources':{name:sha(attempt/name) for name in SOURCES}}


def audit(wait_attempt,advance_attempt):
    wait=one(wait_attempt,CASES[0]);advance=one(advance_attempt,CASES[1])
    fixed=('crossing_id','roadway_id','ego_highway','other_highway',
           'ego_side','other_side','approach_relation',
           'official_device_controls_intersection','other_left_turn_intent',
           'subsection_4_context_reviewed','intersection_polygon_xy_m')
    if (wait['diagnostic_fixture']!=advance['diagnostic_fixture'] or
            any(wait['site'].get(k)!=advance['site'].get(k) for k in fixed) or
            wait['sources']['road.xodr']!=advance['sources']['road.xodr'] or
            wait['sources']['other-body-history.jsonl']!=advance['sources']['other-body-history.jsonl'] or
            wait['sources']['video_frames.jsonl']!=advance['sources']['video_frames.jsonl']):
        raise ValueError('fixed source or crossing conditions changed')
    if (wait['policy']!='wait_for_other_clear' or
            advance['policy']!='advance_at_release' or
            not wait['ego_brake_all_other_inside'] or
            not advance['ego_released_while_other_inside']):
        raise ValueError('declared original controlled-policy difference not observed')
    return {'format':'worker-c125714-independent-policy-comparison-v1',
            'case_ids':list(CASES),'source_sha256':[wait['sources'],advance['sources']],
            'other_inside_frames':[wait['other_inside_frames'],advance['other_inside_frames']],
            'observed_difference':'ego brake held versus released while other body occupied crossing',
            'diagnostic_fixture':wait['diagnostic_fixture'],
            'right_of_way_yielding':'unresolved',
            'legal_verdict_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--wait-attempt',required=True)
    parser.add_argument('--advance-attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    result=audit(args.wait_attempt,args.advance_attempt)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
