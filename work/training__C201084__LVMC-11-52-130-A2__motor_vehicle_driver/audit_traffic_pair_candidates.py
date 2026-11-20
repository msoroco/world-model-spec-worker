"""Audit exact four-candidate CPU proofs and the controlled lead-presence pair."""
import hashlib
import json
from pathlib import Path

from traffic_pair_controller import request
from traffic_pair_entrypoint import TUNINGS

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
IDS=('primary','fallback1','fallback2','fallback3')
MODES=('near_lead','absent_lead')
CAMERAS=('overview','approach','reference_corner','driver_reference')
CHANNELS=('ego_pose','ego_speed','vehicle_stops_in_posted_fire_lane',
          'lead_traffic_presence')
FIXED_ACTOR=('frame','source_kind','ego_actor_id','driving_road_id',
             'ego_pose_xyz_m','ego_yaw_deg','following_actor_id',
             'following_road_id','following_velocity_xyz_mps',
             'following_body_vertices_xyz_m','following_gap_m',
             'sign_actor_id','ego_velocity_xyz_mps','ego_body_vertices_xyz_m',
             'physical_completion_claimed','statutory_necessity_claimed')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def rows(path):return [json.loads(x) for x in path.read_text().splitlines() if x]
def require(value,message):
    if not value:raise ValueError(message)


def audit():
    output={}
    pair={}
    for mode in MODES:
        case=HERE.name+'__'+mode
        manifest_path=HERE/('draft-'+mode+'-fallback-manifest.json')
        entry,=read(manifest_path)['cases']
        require(entry['case_id']==case and
                {x['id'] for x in entry['candidates']}==set(IDS[1:]),
                mode+' candidate set differs')
        selections={'primary':entry}
        selections.update({x['id']:x for x in entry['candidates']})
        source_hashes=None
        constructions=set()
        tunings=set()
        candidate_audit={}
        for ident in IDS:
            item=selections[ident]
            construction_path=HERE/item['construction']
            checksum=sha(construction_path)
            require(checksum==item['construction_sha256'],
                    mode+'/'+ident+' construction hash differs')
            constructions.add(checksum)
            construction=read(construction_path)
            config=next(json.loads(x['content']) for x in construction['files']
                        if x['path']=='config.json')
            tuning=config.get('traffic_pair_controller_tuning',{})
            require(config['candidate_id']==ident and
                    config['case_id']==case and
                    tuning==TUNINGS[mode][ident] and
                    config['frames']==600 and config['rate_hz']==20 and
                    len(config['cameras'])==4,
                    mode+'/'+ident+' exact control or capture differs')
            tunings.add(json.dumps(tuning,sort_keys=True))
            stem='c201084-update111-'+mode+'-'+ident
            offline=ROOT/'.runtime-work'/(stem+'-offline')
            compat=ROOT/'.runtime-work'/(stem+'-compatibility')
            saved=ROOT/'.runtime-work'/(stem+'-saved')/'v0001'
            for selection_path in (offline/'candidate-selection.json',
                                   compat/'candidate-selection.json'):
                selected=read(selection_path)
                require(selected['candidate_id']==ident and
                        selected['case_id']==case and
                        selected['construction_sha256']==checksum and
                        selected['manifest_sha256']==sha(manifest_path),
                        mode+'/'+ident+' selected bundle differs')
            comp=read(compat/'compatibility.json')
            receipt=read(saved/'processing.json')
            require(comp['passed'] is True and
                    comp['candidate_id']==ident and
                    comp['construction_sha256']==checksum and
                    comp['negative_removed']=='native-survey-readback.json' and
                    'negative_case_source' in comp['checks'],
                    mode+'/'+ident+' positive/negative compatibility differs')
            require(receipt['passed'] is True and
                    receipt['recorded_only'] is True and
                    receipt['originals_preserved'] is True and
                    receipt['missing_evidence'] is False and
                    receipt['timestamp_joins']['frames']==600 and
                    receipt['timestamp_joins']['passed'] is True and
                    receipt['physical_acceptance_claimed'] is False and
                    receipt['legal_acceptance_claimed'] is False and
                    receipt['analysis_revision']['construction_sha256']==checksum,
                    mode+'/'+ident+' saved proof differs')
            analysis=saved/'analysis'
            result=read(analysis/'result.json')
            report=read(analysis/'analysis-report.json')
            measured=report['measurements']['traffic_pair_context']['value']
            present=mode=='near_lead'
            require(result['accepted'] is False and
                    result['physical_acceptance_claimed'] is False and
                    result['legal_verdict_claimed'] is False and
                    result['measured_values']['source_frames']==600 and
                    measured['lead_present'] is present and
                    measured['lead_ahead_frames']==(600 if present else 0) and
                    measured['lead_brake_request_frames']==(1 if present else 0) and
                    measured['statutory_necessity_verified'] is False and
                    report['analysis_complete'] is True and
                    report['diagnostic_fixture'] is True,
                    mode+'/'+ident+' result overclaims or source relation differs')
            require(all(len(rows(analysis/'channels'/(name+'.jsonl')))==600
                        for name in CHANNELS),
                    mode+'/'+ident+' source-derived channel length differs')
            hashes={name:sha(analysis/name) for name in
                    ('native-actors.jsonl','video_frames.jsonl',
                     'native-survey-readback.json',
                     *[camera+'.mkv' for camera in CAMERAS])}
            require(all(result['physical_checks'][key]['sources'][name]==checksum
                        for key in ('setup','target','maneuver')
                        for name,checksum in hashes.items()),
                    mode+'/'+ident+' physical-check source hashes differ')
            if source_hashes is None:source_hashes=hashes
            require(hashes==source_hashes,
                    mode+'/'+ident+' source changed across candidate selection')
            if ident=='primary':
                actors=rows(analysis/'native-actors.jsonl')
                survey=read(analysis/'native-survey-readback.json')
                for actor in actors:
                    require(actor['source_kind']=='synthetic_native_sample' and
                            actor['lead_present'] is present,
                            mode+' diagnostic provenance or lead inventory differs')
                    if present:
                        require(type(actor.get('lead_actor_id')) is int,
                                mode+' lead actor ID missing')
                    else:
                        require(not any(k.startswith('lead_') for k in actor
                                        if k!='lead_present'),
                                mode+' hidden lead actor field')
                    expected=request(actor['ego_pose_xyz_m'][:2],
                                     actor['ego_yaw_deg'],
                                     actor['ego_velocity_xyz_mps'],[30,1],
                                     lead_xy_m=actor['lead_pose_xyz_m'][:2] if present else None,
                                     lead_velocity_xyz_mps=actor['lead_velocity_xyz_mps'] if present else None)
                    require(actor['requested_control']==expected,
                            mode+' primary request differs at frame '+str(actor['frame']))
                pair[mode]={'actors':actors,'survey':survey,
                            'map':rows(analysis/'video_frames.jsonl'),
                            'cameras':{name:hashes[name+'.mkv'] for name in CAMERAS}}
            candidate_audit[ident]={
                'construction_sha256':checksum,
                'compatibility_receipt_sha256':sha(compat/'compatibility.json'),
                'saved_receipt_sha256':sha(saved/'processing.json'),
                'lead_present':present,
                'lead_brake_request_frames':measured['lead_brake_request_frames']}
        require(len(constructions)==len(tunings)==4,
                mode+' fallback construction or tuning repeats')
        output[mode]={'manifest_sha256':sha(manifest_path),
                      'candidate_count':4,'candidates':candidate_audit,
                      'source_sha256':source_hashes}
    near,absent=pair['near_lead'],pair['absent_lead']
    require(near['map']==absent['map'] and near['cameras']==absent['cameras'],
            'Pair clocks or four source cameras differ')
    require(all(all(a[key]==b[key] for key in FIXED_ACTOR)
                for a,b in zip(near['actors'],absent['actors'])),
            'Pair fixed ego/follower/sign samples differ')
    for key in ('map_name','fixed_context','sign_readback','survey_geometry',
                'camera_names','capture_frames','capture_hz'):
        require(near['survey'][key]==absent['survey'][key],
                'Pair fixed survey differs: '+key)
    return {'format':'c201084-four-candidate-lead-presence-audit-v1',
            'passed':True,'modes':output,'pair_frames':600,
            'fixed_camera_sources':list(CAMERAS),
            'synthetic_native_sample':True,
            'canonical_comparison_audit':False,
            'physical_or_legal_acceptance_claimed':False}


if __name__=='__main__':
    print(json.dumps(audit(),indent=2,sort_keys=True))
