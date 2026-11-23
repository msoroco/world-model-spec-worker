"""Recompute the diagnostic lead-presence comparison on final attempts."""
import hashlib
import json
from pathlib import Path

from traffic_pair_controller import request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
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


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit():
    manifest_path = HERE / 'execution-manifest.json'
    manifest_sha = sha(manifest_path)
    chain_path = HERE / 'final-chains-audit.json'
    chains = read(chain_path)
    require(chains['passed'] is True and
            chains['final_manifest_sha256'] == manifest_sha,
            'Final candidate audit differs')
    sources = {}
    for mode in ('near_lead', 'absent_lead'):
        case_id = HERE.name + '__' + mode
        entry = next(row for row in read(manifest_path)['cases']
                     if row['case_id'] == case_id)
        compat = REPO / '.runtime-work' / ('c201084-final-' + mode + '-primary-compatibility')
        saved = REPO / '.runtime-work' / ('c201084-final-' + mode + '-primary-saved/v0001')
        comp = read(compat / 'compatibility.json')
        receipt = read(saved / 'processing.json')
        selection = read(compat / 'candidate-selection.json')
        proof_path = HERE / ('final-' + mode + '-primary-proof.json')
        require(selection['manifest_sha256'] == manifest_sha and
                selection['case_id'] == case_id and
                selection['candidate_id'] == 'primary' and
                selection['construction_sha256'] == entry['construction_sha256'] and
                chains['candidate_proof_sha256'][mode + '/primary'] == sha(proof_path),
                mode + ' final identity differs')
        require(comp['passed'] is True and
                comp['negative_removed'] == 'native-survey-readback.json' and
                'Missing required source' in comp['negative_error_contains'] and
                receipt['passed'] is True and receipt['recorded_only'] is True and
                receipt['originals_preserved'] is True and
                receipt['timestamp_joins']['frames'] == 600 and
                receipt['physical_acceptance_claimed'] is False and
                receipt['legal_acceptance_claimed'] is False,
                mode + ' CPU receipt differs')
        survey = read(compat / 'native-survey-readback.json')
        require(survey['traffic_pair']['lead_present'] is (mode == 'near_lead') and
                survey['traffic_pair']['statutory_necessity_verified'] is False,
                mode + ' source plan differs')
        actors = rows(compat / 'native-actors.jsonl')
        mapping = rows(compat / 'video_frames.jsonl')
        require(len(actors) == len(mapping) == 600 and
                all(actor['source_kind'] == 'synthetic_native_sample' for actor in actors),
                mode + ' frame provenance differs')
        for actor in actors:
            lead = mode == 'near_lead'
            require(actor['lead_present'] is lead and
                    (type(actor.get('lead_actor_id')) is int if lead else
                     not any(key.startswith('lead_') for key in actor
                             if key != 'lead_present')),
                    mode + ' lead inventory differs')
            expected = request(actor['ego_pose_xyz_m'][:2], actor['ego_yaw_deg'],
                               actor['ego_velocity_xyz_mps'], [30, 1],
                               lead_xy_m=actor['lead_pose_xyz_m'][:2] if lead else None,
                               lead_velocity_xyz_mps=actor['lead_velocity_xyz_mps'] if lead else None)
            require(actor['requested_control'] == expected,
                    mode + ' control request differs at frame ' + str(actor['frame']))
        measured = read(saved / 'analysis/analysis-report.json')['measurements']['traffic_pair_context']['value']
        require(measured['lead_present'] is (mode == 'near_lead') and
                measured['lead_ahead_frames'] == (600 if mode == 'near_lead' else 0) and
                measured['lead_brake_request_frames'] == (1 if mode == 'near_lead' else 0) and
                measured['statutory_necessity_verified'] is False,
                mode + ' saved measurement differs')
        camera_hashes = {name: sha(compat / (name + '.mkv')) for name in CAMERAS}
        require(all(receipt['original_source_hashes'][name + '.mkv'] == digest
                    for name, digest in camera_hashes.items()),
                mode + ' camera source differs')
        sources[mode] = {'actors': actors, 'mapping': mapping, 'survey': survey,
                         'cameras': camera_hashes,
                         'selection_sha256': sha(compat / 'candidate-selection.json'),
                         'saved_receipt_sha256': sha(saved / 'processing.json')}
    near, absent = sources['near_lead'], sources['absent_lead']
    require(near['mapping'] == absent['mapping'] and
            near['cameras'] == absent['cameras'] and
            all(all(a[key] == b[key] for key in FIXED_ACTOR)
                for a, b in zip(near['actors'], absent['actors'])),
            'Final lead pair changed fixed samples or cameras')
    for key in ('map_name', 'fixed_context', 'sign_readback', 'survey_geometry',
                'camera_names', 'capture_frames', 'capture_hz'):
        require(near['survey'][key] == absent['survey'][key],
                'Final lead pair changed fixed survey: ' + key)
    return {'format': 'c201084-final-traffic-pair-cpu-audit-v1',
            'passed': True, 'diagnostic_only': True, 'accepted': False,
            'final_manifest_sha256': manifest_sha,
            'final_chains_audit_sha256': sha(chain_path),
            'near_lead_selection_sha256': near['selection_sha256'],
            'absent_lead_selection_sha256': absent['selection_sha256'],
            'near_lead_saved_receipt_sha256': near['saved_receipt_sha256'],
            'absent_lead_saved_receipt_sha256': absent['saved_receipt_sha256'],
            'frames': 600, 'fixed_source_camera_sha256': near['cameras'],
            'near_lead_brake_request_frames': 1,
            'absent_lead_brake_request_frames': 0,
            'original_native_observed': False,
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    (HERE / 'final-traffic-pair-audit.json').write_text(
        json.dumps(audit(), indent=2, sort_keys=True) + '\n')
