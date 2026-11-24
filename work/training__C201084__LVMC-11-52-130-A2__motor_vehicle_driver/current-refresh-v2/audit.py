"""Audit current-runtime selected receipts and controlled diagnostic pairs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
REPO = PACKAGE.parents[1]
SCRATCH = REPO / '.runtime-work/c201084-refresh-v2'
GROUPS = ('reference', 'contrast', 'conflict', 'clear', 'near_lead',
          'absent_lead', 'device_direction', 'officer_direction')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
PAIRS = (('reference', 'contrast', 'vehicle_stops_in_posted_fire_lane'),
         ('conflict', 'clear', 'lead_spawn_xy_m'),
         ('near_lead', 'absent_lead', 'lead_traffic_presence'))
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def audit():
    manifest_path = PACKAGE / 'execution-manifest.json'
    manifest = read(manifest_path)
    runtime_sha = sha(REPO / 'runtime/SOURCE-MANIFEST.json')
    require(manifest['runtime_manifest_sha256'] == runtime_sha, 'Runtime changed')
    cases = {row['case_id'].rsplit('__', 1)[-1]: row for row in manifest['cases']}
    require(set(cases) == set(GROUPS), 'Selected cases changed')
    bindings = {}
    for group, case in cases.items():
        for candidate in CANDIDATES:
            plan = case if candidate == 'primary' else next(
                row for row in case['candidates'] if row['id'] == candidate)
            prefix = group + '-' + candidate
            offline = HERE / (prefix + '-offline.json')
            selection = HERE / (prefix + '-selection.json')
            compat = HERE / (prefix + '-compatibility.json')
            analysis = HERE / (prefix + '-analysis.log')
            negative = HERE / (prefix + '-negative.log')
            saved = HERE / (prefix + '-saved.json')
            proof = HERE / (prefix + '-proof.json')
            files = (offline, selection, compat, analysis, negative, saved)
            require(all(path.is_file() and path.stat().st_size <= 2 * 1024 * 1024
                        for path in (*files, proof)), 'Missing/oversize chain: ' + prefix)
            o, s, c, v, p = map(read, (offline, selection, compat, saved, proof))
            require(o['offline_passed'] is True and o['simulation_started'] is False and
                    o['case_id'] == case['case_id'] and o['candidate_id'] == candidate,
                    'Offline differs: ' + prefix)
            require(s['case_id'] == case['case_id'] and s['candidate_id'] == candidate and
                    s['construction_sha256'] == plan['construction_sha256'],
                    'Selection differs: ' + prefix)
            require(c['passed'] is True and c['scope'] == 'diagnostic software compatibility only' and
                    c['runtime_manifest_sha256'] == runtime_sha and
                    c['construction_sha256'] == plan['construction_sha256'] and
                    c['negative_log_sha256'] == sha(negative) and
                    c['negative_error_contains'] in negative.read_text(),
                    'Public positive/negative differs: ' + prefix)
            require(v['passed'] is True and v['recorded_only'] is True and
                    v['originals_preserved'] is True and
                    v['analysis_revision']['runtime_manifest_sha256'] == runtime_sha and
                    v['native_revision']['construction_sha256'] == plan['construction_sha256'] and
                    v['physical_acceptance_claimed'] is False and
                    v['legal_acceptance_claimed'] is False,
                    'Saved processing differs: ' + prefix)
            require(p['passed'] is True and p['runtime_manifest_sha256'] == runtime_sha and
                    all(p['receipts'][path.name] == sha(path) for path in files),
                    'Durable proof differs: ' + prefix)
            require(plan['offline']['log_sha256'] == sha(offline) and
                    plan['compatibility']['sha256'] == sha(compat) and
                    plan['saved_processing']['sha256'] == sha(saved),
                    'Manifest receipt binding differs: ' + prefix)
            bindings[prefix] = {path.name: sha(path) for path in (*files, proof)}

    comparisons = []
    plan = read(PACKAGE / 'case-plan.json')
    for left, right, deliberate in PAIRS:
        spec = next(row for row in plan['comparisons'] if
                    row['case_ids'] == [cases[left]['case_id'], cases[right]['case_id']])
        require(spec['deliberate_differences'] == [deliberate],
                'Comparison difference changed: ' + left)
        a = SCRATCH / (left + '-primary-compat')
        b = SCRATCH / (right + '-primary-compat')
        require(a.is_dir() and b.is_dir(), 'Source attempt unavailable: ' + left)
        source_hashes = {}
        for name in CAMERAS:
            key = name + '.mkv'
            x, y = sha(a / key), sha(b / key)
            require(x == y, 'Fixed camera changed: ' + left + '/' + name)
            require(read(HERE / (left + '-primary-saved.json'))['original_source_hashes'][key] == x and
                    read(HERE / (right + '-primary-saved.json'))['original_source_hashes'][key] == y,
                    'Saved source hash differs: ' + left + '/' + name)
            source_hashes[key] = x
        frames_a = (a / 'video_frames.jsonl').read_bytes()
        frames_b = (b / 'video_frames.jsonl').read_bytes()
        require(frames_a == frames_b, 'Fixed frame map changed: ' + left)
        survey_a, survey_b = read(a / 'native-survey-readback.json'), read(b / 'native-survey-readback.json')
        for key in ('map_name', 'capture_frames', 'capture_hz', 'camera_names',
                    'survey_geometry', 'fixed_context', 'sign_readback'):
            require(survey_a[key] == survey_b[key], 'Fixed survey changed: ' + left + '/' + key)
        actors_a = [json.loads(line) for line in (a / 'native-actors.jsonl').read_text().splitlines()]
        actors_b = [json.loads(line) for line in (b / 'native-actors.jsonl').read_text().splitlines()]
        require(len(actors_a) == len(actors_b) == 600, 'Actor frame count differs: ' + left)
        if deliberate == 'vehicle_stops_in_posted_fire_lane':
            for i, (x, y) in enumerate(zip(actors_a, actors_b)):
                moved = json.loads(json.dumps(x))
                moved['ego_pose_xyz_m'][0] += 14
                for field in ('ego_body_vertices_xyz_m', 'following_body_vertices_xyz_m'):
                    for vertex in moved[field]:
                        vertex[0] += 14
                require(moved == y, 'Stop comparison changed another actor field: ' + str(i))
        else:
            fixed = ('frame', 'source_kind', 'ego_actor_id', 'driving_road_id',
                     'ego_pose_xyz_m', 'ego_yaw_deg', 'following_actor_id',
                     'following_road_id', 'following_velocity_xyz_mps',
                     'following_body_vertices_xyz_m', 'following_gap_m',
                     'sign_actor_id', 'ego_velocity_xyz_mps', 'ego_body_vertices_xyz_m')
            require(all(all(x.get(key) == y.get(key) for key in fixed)
                        for x, y in zip(actors_a, actors_b)),
                    'Comparison changed fixed actor samples: ' + left)
        comparisons.append({'comparison_id': spec['comparison_id'],
                            'deliberate_difference': deliberate,
                            'left_selection_sha256': sha(a / 'candidate-selection.json'),
                            'right_selection_sha256': sha(b / 'candidate-selection.json'),
                            'fixed_camera_sha256': source_hashes,
                            'fixed_frame_map_sha256': sha(a / 'video_frames.jsonl'),
                            'diagnostic_only': True, 'accepted': False})
    return {'format': 'c201084-current-runtime-source-audit-v1', 'passed': True,
            'runtime_manifest_sha256': runtime_sha,
            'selected_manifest_sha256': sha(manifest_path),
            'candidate_chains_proven': 32, 'selected_cases': 8,
            'candidate_receipts_sha256': bindings, 'controlled_comparisons': comparisons,
            'original_native_observed': False, 'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    output = HERE / 'audit.json'
    output.write_text(json.dumps(audit(), indent=2, sort_keys=True) + '\n')
    print(sha(output))
