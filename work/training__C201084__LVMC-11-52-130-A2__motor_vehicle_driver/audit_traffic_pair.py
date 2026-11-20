"""Independent source and receipt audit for the draft lead-presence pair."""
import hashlib
import json
from pathlib import Path

from traffic_pair_controller import request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FIXED_ACTOR = ('frame', 'source_kind', 'ego_actor_id', 'driving_road_id',
               'ego_pose_xyz_m', 'ego_yaw_deg', 'following_actor_id',
               'following_road_id', 'following_velocity_xyz_mps',
               'following_body_vertices_xyz_m', 'following_gap_m',
               'sign_actor_id', 'ego_velocity_xyz_mps',
               'ego_body_vertices_xyz_m', 'physical_completion_claimed',
               'statutory_necessity_claimed')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit():
    sources = {}
    for mode in ('near_lead', 'absent_lead'):
        manifest = HERE/('draft-'+mode+'-manifest.json')
        entry = load(manifest)['cases'][0]
        construction = HERE/entry['construction']
        require(entry['construction_sha256'] == sha(construction),
                mode+' construction hash differs')
        compat = ROOT/'.runtime-work'/('c201084-update110-'+mode+'-compatibility')
        saved_root = ROOT/'.runtime-work'/('c201084-update110-'+mode+'-saved')
        versions = [version for version in saved_root.glob('v*')
                    if (version/'processing.json').is_file()]
        require(len(versions) == 1, mode+' has no unique successful saved version')
        saved = versions[0]
        comp = load(compat/'compatibility.json')
        receipt = load(saved/'processing.json')
        require(comp['passed'] is True and
                comp['construction_sha256'] == sha(construction) and
                comp['negative_removed'] == 'native-survey-readback.json' and
                'Missing required source' in comp['negative_error_contains'],
                mode+' exact positive/negative compatibility differs')
        require(receipt['passed'] is True and
                receipt['recorded_only'] is True and
                receipt['missing_evidence'] is False and
                receipt['originals_preserved'] is True and
                receipt['timestamp_joins']['frames'] == 600 and
                receipt['timestamp_joins']['passed'] is True and
                receipt['physical_acceptance_claimed'] is False and
                receipt['legal_acceptance_claimed'] is False and
                receipt['analysis_revision']['construction_sha256'] == sha(construction),
                mode+' recorded-only proof differs')
        survey = load(compat/'native-survey-readback.json')
        pair = survey['traffic_pair']
        require(pair['lead_present'] is (mode == 'near_lead') and
                pair['destination_xy_m'] == [30, 1] and
                pair['statutory_necessity_verified'] is False,
                mode+' source plan differs')
        actors = rows(compat/'native-actors.jsonl')
        mapping = rows(compat/'video_frames.jsonl')
        require(len(actors) == len(mapping) == 600 and
                all(a['source_kind'] == 'synthetic_native_sample' for a in actors),
                mode+' frame or provenance differs')
        for actor in actors:
            lead = mode == 'near_lead'
            require(actor['lead_present'] is lead and
                    (type(actor.get('lead_actor_id')) is int if lead else
                     not any(k.startswith('lead_') for k in actor if k != 'lead_present')),
                    mode+' actor inventory differs')
            expected = request(actor['ego_pose_xyz_m'][:2], actor['ego_yaw_deg'],
                               actor['ego_velocity_xyz_mps'], [30, 1],
                               lead_xy_m=actor['lead_pose_xyz_m'][:2] if lead else None,
                               lead_velocity_xyz_mps=actor['lead_velocity_xyz_mps'] if lead else None)
            require(actor['requested_control'] == expected,
                    mode+' source control request differs at frame '+str(actor['frame']))
        measured = load(saved/'analysis/analysis-report.json')['measurements']['traffic_pair_context']['value']
        require(measured['lead_present'] is (mode == 'near_lead') and
                measured['lead_ahead_frames'] == (600 if mode == 'near_lead' else 0) and
                measured['lead_brake_request_frames'] == (1 if mode == 'near_lead' else 0) and
                measured['statutory_necessity_verified'] is False,
                mode+' saved traffic context differs')
        for name in CAMERAS:
            require(receipt['original_source_hashes'][name+'.mkv'] ==
                    sha(compat/(name+'.mkv')),
                    mode+' camera source hash differs: '+name)
        sources[mode] = {'actors': actors, 'mapping': mapping, 'survey': survey,
                         'compatibility': comp, 'saved': receipt,
                         'camera_hashes': {name: sha(compat/(name+'.mkv')) for name in CAMERAS}}
    near, absent = sources['near_lead'], sources['absent_lead']
    require(near['mapping'] == absent['mapping'] and
            near['camera_hashes'] == absent['camera_hashes'],
            'Pair source clocks or camera pixels differ')
    require(all(all(a[key] == b[key] for key in FIXED_ACTOR)
                for a, b in zip(near['actors'], absent['actors'])),
            'Pair fixed ego/follower/sign samples differ')
    for key in ('map_name', 'fixed_context', 'sign_readback', 'survey_geometry',
                'camera_names', 'capture_frames', 'capture_hz'):
        require(near['survey'][key] == absent['survey'][key],
                'Pair fixed survey differs: '+key)
    return {'format':'c201084-draft-traffic-pair-audit-v1', 'passed':True,
            'cases':list(sources), 'frames':600,
            'fixed_source_cameras':list(CAMERAS),
            'same_decoded_source_video_hashes':True,
            'near_lead_brake_request_frames':1,
            'absent_lead_brake_request_frames':0,
            'recorded_only_saved_processing':True,
            'synthetic_native_sample':True,
            'physical_acceptance_claimed':False,
            'legal_acceptance_claimed':False,
            'canonical_comparison_audit':False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2, sort_keys=True))
