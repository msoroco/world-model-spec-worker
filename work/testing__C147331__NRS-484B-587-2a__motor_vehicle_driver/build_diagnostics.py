"""Produce source-hashed textual nine-frame diagnostics for every exact case."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from author_semantic import AID, HERE
from outside_lane import CASES

ROOT = HERE.parents[1]


def checksum(data):
    return sha256(data if isinstance(data,bytes) else data.encode()).hexdigest()


def encode(value):
    return json.dumps(value,indent=2,ensure_ascii=False)+'\n'


def run():
    base=json.loads((ROOT/'runtime/fixtures/example.json').read_text())
    assignment=ROOT/'inputs'/AID/'assignment.json'
    source_hash=checksum(assignment.read_bytes())
    for case in CASES:
        suffix=case.name
        folder=HERE if suffix==CASES[0].name else HERE/'cases'/suffix
        generator=deepcopy(base)
        case_id=AID+'__'+suffix
        trace=[json.loads(line) for line in generator['files']['trace.jsonl'].splitlines()]
        frames=[json.loads(line) for line in generator['files']['video_frames.jsonl'].splitlines()]
        if len(trace)!=len(frames) or len(trace)<2:
            raise ValueError('base structural fixture frames differ')
        synthetic={role:checksum('synthetic C147331 '+role) for role in (
            'map','markings','designation','boundary','direction','sign','emergency','authorization','camera','packet')}
        route_lateral={'traffic_lane':1.75,'outside_nonshoulder':7.5,
                       'paved_shoulder':5.5,'entrance_lane':1.75,'exit_lane':1.75}[case.route_class]
        rows=[]
        for motion,mapped in zip(trace,frames):
            row={'case':suffix,'ego_id':'synthetic-ego','map_sha256':synthetic['map'],
                 'lane_marking_source_sha256':synthetic['markings'],
                 'legal_controlled_access_source_sha256':synthetic['designation'],
                 'public_highway_boundary_source_sha256':synthetic['boundary'],
                 'direction_source_sha256':synthetic['direction'],
                 'camera_plan_sha256':synthetic['camera'],
                 'sign_source_sha256':synthetic['sign'],
                 'emergency_record_source_sha256':synthetic['emergency'],
                 'subsection3_authorization_source_sha256':synthetic['authorization'],
                 'vehicle_class':case.vehicle_class,'approach':case.approach,
                 'route_class':case.route_class,
                 'sign_permits_shoulder':case.sign_permits_shoulder,
                 'emergency_required':case.emergency_required,
                 'subsection3_authorized':case.subsection3_authorized,
                 'original_frame':motion['frame'],'source_sha256':source_hash,
                 'capture_packet_sha256':synthetic['packet'],
                 'ego_lateral_m':route_lateral,
                 'ego_speed_mps':motion['speed_mps'],
                 'left_marking_lateral_m':0.0,
                 'right_marking_lateral_m':3.5,
                 'shoulder_outer_lateral_m':7.0}
            if motion['frame']!=mapped['carla_frame']:
                raise ValueError('structural fixture frame join differs')
            rows.append(row)
        history=''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows)
        generator['files']['original-history.jsonl']=history
        manifest=json.loads(generator['files']['capture/manifest.json'])
        manifest['case_id']=case_id
        manifest['source_run']='fixture:C147331-source-gated-lane-'+suffix
        generator['files']['capture/manifest.json']=encode(manifest)
        generator['files']['original-source-receipt.json']=encode({
            'source_kind':'synthetic_diagnostic_fixture','diagnostic_fixture':True,
            'case_id':case_id,'frame_count':len(rows),
            'history_sha256':checksum(history),
            'trace_sha256':checksum(generator['files']['trace.jsonl']),
            'frame_map_sha256':checksum(generator['files']['video_frames.jsonl']),
            'shoulder_paved_source_sha256':checksum('synthetic C147331 paving'),
            'source_limit':'Synthetic lane positions and legal context are not original Native evidence'})
        gen_path=folder/'fixture-generator.json'
        gen_path.write_text(json.dumps(generator,separators=(',',':'),ensure_ascii=False)+'\n')
        recipe={'format':'worker-fixture-recipe',
                'sources':[{'path':'diagnostic-law-source.json',
                            'source':str(assignment.relative_to(ROOT)),
                            'sha256':source_hash}],
                'generator':{'source':str(gen_path.relative_to(ROOT)),
                             'sha256':checksum(gen_path.read_bytes())}}
        (folder/'fixture-recipe.json').write_text(encode(recipe))


if __name__=='__main__':run()
