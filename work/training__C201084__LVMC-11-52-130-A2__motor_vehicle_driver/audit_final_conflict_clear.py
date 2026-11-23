"""Audit the selected lead-position diagnostic comparison from retained sources."""
import hashlib
import json
from pathlib import Path

from conflict_controller import decision

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FIXED_ACTOR = ('frame', 'source_kind', 'ego_actor_id', 'driving_road_id',
               'ego_pose_xyz_m', 'ego_yaw_deg', 'following_actor_id',
               'following_road_id', 'following_velocity_xyz_mps',
               'following_body_vertices_xyz_m', 'following_gap_m',
               'sign_actor_id', 'ego_velocity_xyz_mps',
               'ego_body_vertices_xyz_m', 'lead_actor_id', 'lead_road_id',
               'lead_lane_id', 'lead_yaw_deg', 'lead_velocity_xyz_mps',
               'physical_completion_claimed', 'statutory_necessity_claimed')


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
    plan = read(HERE / 'case-plan.json')
    comparison = next(row for row in plan['comparisons']
                      if row['comparison_id'] == HERE.name + '__comparison_lead_position')
    require(comparison['case_ids'] == [HERE.name + '__conflict', HERE.name + '__clear'] and
            comparison['deliberate_differences'] == ['lead_spawn_xy_m'],
            'Lead-position comparison plan differs')
    sources = {}
    for mode in ('conflict', 'clear'):
        case_id = HERE.name + '__' + mode
        entry = next(row for row in read(manifest_path)['cases'] if row['case_id'] == case_id)
        compat = REPO / '.runtime-work' / ('c201084-final-' + mode + '-primary-compatibility')
        saved = REPO / '.runtime-work' / ('c201084-final-' + mode + '-primary-saved/v0001')
        receipt = read(saved / 'processing.json')
        comp = read(compat / 'compatibility.json')
        selection = read(compat / 'candidate-selection.json')
        proof_path = HERE / ('final-' + mode + '-primary-proof.json')
        require(selection['manifest_sha256'] == manifest_sha and
                selection['case_id'] == case_id and
                selection['construction_sha256'] == entry['construction_sha256'] and
                chains['candidate_proof_sha256'][mode + '/primary'] == sha(proof_path),
                mode + ' selected binding differs')
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
        probe = survey['conflict_probe']
        require(probe['lead_spawn_xy_m'] == ([18, 1] if mode == 'conflict' else [35, 1]) and
                probe['statutory_necessity_verified'] is False and
                probe['original_review_required'] is True,
                mode + ' lead-position plan differs')
        actors = rows(compat / 'native-actors.jsonl')
        mapping = rows(compat / 'video_frames.jsonl')
        require(len(actors) == len(mapping) == 600 and
                all(actor['source_kind'] == 'synthetic_native_sample' for actor in actors),
                mode + ' source frame provenance differs')
        for actor in actors:
            expected = decision(actor['ego_pose_xyz_m'][:2],
                                actor['ego_velocity_xyz_mps'][:2],
                                actor['lead_pose_xyz_m'][:2],
                                actor['lead_velocity_xyz_mps'][:2],
                                actor['ego_yaw_deg'])
            require(actor['requested_control'] == expected,
                    mode + ' source controller differs at frame ' + str(actor['frame']))
        measured = read(saved / 'analysis/analysis-report.json')['measurements']['lead_conflict_context']['value']
        require(measured['lead_ahead_frames'] == 600 and
                measured['brake_request_frames'] == (1 if mode == 'conflict' else 0) and
                measured['near_zero_with_zone_overlap_frames'] == 598 and
                measured['statutory_necessity_verified'] is False,
                mode + ' saved lead-context measurement differs')
        cameras = {name: sha(compat / (name + '.mkv')) for name in CAMERAS}
        require(all(receipt['original_source_hashes'][name + '.mkv'] == digest
                    for name, digest in cameras.items()),
                mode + ' original camera differs')
        sources[mode] = {'actors': actors, 'mapping': mapping, 'survey': survey,
                         'cameras': cameras,
                         'selection_sha256': sha(compat / 'candidate-selection.json'),
                         'saved_receipt_sha256': sha(saved / 'processing.json')}
    conflict, clear = sources['conflict'], sources['clear']
    require(conflict['mapping'] == clear['mapping'] and
            conflict['cameras'] == clear['cameras'] and
            all(all(a[key] == b[key] for key in FIXED_ACTOR)
                for a, b in zip(conflict['actors'], clear['actors'])),
            'Lead-position pair changed fixed actors or cameras')
    for key in ('map_name', 'fixed_context', 'sign_readback', 'survey_geometry',
                'camera_names', 'capture_frames', 'capture_hz'):
        require(conflict['survey'][key] == clear['survey'][key],
                'Lead-position pair changed fixed survey: ' + key)
    require(conflict['survey']['conflict_probe']['lead_blueprint'] ==
            clear['survey']['conflict_probe']['lead_blueprint'],
            'Lead-position pair changed lead blueprint')
    return {'format': 'c201084-final-conflict-clear-cpu-audit-v1',
            'passed': True, 'diagnostic_only': True, 'accepted': False,
            'final_manifest_sha256': manifest_sha,
            'final_chains_audit_sha256': sha(chain_path),
            'comparison_id': comparison['comparison_id'],
            'conflict_selection_sha256': conflict['selection_sha256'],
            'clear_selection_sha256': clear['selection_sha256'],
            'conflict_saved_receipt_sha256': conflict['saved_receipt_sha256'],
            'clear_saved_receipt_sha256': clear['saved_receipt_sha256'],
            'fixed_source_camera_sha256': conflict['cameras'],
            'conflict_brake_request_frames': 1,
            'clear_brake_request_frames': 0,
            'original_native_observed': False,
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    (HERE / 'final-conflict-clear-audit.json').write_text(
        json.dumps(audit(), indent=2, sort_keys=True) + '\n')
