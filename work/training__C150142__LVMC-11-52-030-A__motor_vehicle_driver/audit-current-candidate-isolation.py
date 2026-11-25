"""Check that selected fallback constructions preserve the case comparison.

This checks authored requests and hashes, not realized CARLA geometry or motion.
"""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CONFIG_CONTROL_KEYS = {'candidate_id', 'risk_trigger', 'tracks_sha256',
                       'requested_target_x_m', 'requested_approach_frames',
                       'camera_policy'}
FIXED_CONSTRUCTION_KEYS = ('actor', 'case_id', 'cell_id', 'law_id',
                           'measurement_plan', 'recording_description',
                           'termination_rules')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def files(construction):
    return {item['path']: item['content'] for item in construction['files']}


def inspect_case(entry, override=None):
    case_id = entry['case_id']
    primary_path = HERE / entry['construction']
    require(sha(primary_path) == entry['construction_sha256'],
            'Selected primary construction changed: ' + case_id)
    primary = json.loads(primary_path.read_text())
    primary_files = files(primary)
    base = json.loads(primary_files['config.json'])
    require(hashlib.sha256(primary_files['requested-tracks.jsonl'].encode()).hexdigest()
            == base['tracks_sha256'], 'Selected primary tracks differ: ' + case_id)
    base_tracks = [json.loads(line) for line in
                   primary_files['requested-tracks.jsonl'].splitlines()]
    require(base['candidate_id'] == 'primary' and base['case_id'] == case_id,
            'Selected primary request differs: ' + case_id)
    require(primary['case_id'] == case_id and base['original_native_observed'] is False,
            'Selected primary provenance differs: ' + case_id)
    rows = []
    for candidate in entry['candidates']:
        candidate_id = candidate['id']
        path = HERE / candidate['construction']
        require(sha(path) == candidate['construction_sha256'],
                'Selected fallback construction changed: ' + case_id + '/' + candidate_id)
        construction = json.loads(path.read_text())
        source_files = files(construction)
        config = json.loads(source_files['config.json'])
        if override is not None:
            override(case_id, candidate_id, config)
        require(set(source_files) == set(primary_files),
                'Selected fallback file set differs: ' + case_id + '/' + candidate_id)
        require(all(construction[key] == primary[key] for key in FIXED_CONSTRUCTION_KEYS),
                'Selected fallback scope differs: ' + case_id + '/' + candidate_id)
        require(all(source_files[name] == primary_files[name]
                    for name in source_files if name not in
                    {'config.json', 'requested-tracks.jsonl', 'tests/test_selected.py'}),
                'Selected fallback implementation differs beyond controls: '
                + case_id + '/' + candidate_id)
        require(config['candidate_id'] == candidate_id and config['case_id'] == case_id,
                'Selected fallback identity differs: ' + case_id + '/' + candidate_id)
        require(hashlib.sha256(source_files['requested-tracks.jsonl'].encode()).hexdigest()
                == config['tracks_sha256'],
                'Selected fallback tracks differ: ' + case_id + '/' + candidate_id)
        tracks = [json.loads(line) for line in
                  source_files['requested-tracks.jsonl'].splitlines()]
        track_controls = {'requested_ego_x_m'}
        if config['requested_approach_frames'] != base['requested_approach_frames']:
            track_controls |= {'requested_parked', 'requested_red_curb_occupancy'}
        require(len(tracks) == len(base_tracks) and all(
                {key: value for key, value in row.items()
                 if key not in track_controls} ==
                {key: value for key, value in other.items()
                 if key not in track_controls}
                for row, other in zip(tracks, base_tracks)),
                'Selected fallback changed fixed track fields: '
                + case_id + '/' + candidate_id)
        require({key: value for key, value in config.items()
                 if key not in CONFIG_CONTROL_KEYS} ==
                {key: value for key, value in base.items()
                 if key not in CONFIG_CONTROL_KEYS},
                'Selected fallback fixed conditions differ: ' + case_id + '/' + candidate_id)
        changed = {key for key in ('requested_target_x_m',
                                   'requested_approach_frames', 'camera_policy')
                   if config[key] != base[key]}
        declared = set(candidate['changed_knobs'])
        require(changed and
                (('requested_target_x_m' in declared) ==
                 ('requested_target_x_m' in changed)) and
                (('requested_approach_frames' in declared) ==
                 ('requested_approach_frames' in changed)) and
                (any('camera' in name for name in declared) ==
                 ('camera_policy' in changed)),
                'Selected fallback declared controls differ: ' + case_id + '/' + candidate_id)
        left = base['painted_curb']['start_x_m'] <= base['requested_target_x_m'] <= base['painted_curb']['end_x_m']
        right = config['painted_curb']['start_x_m'] <= config['requested_target_x_m'] <= config['painted_curb']['end_x_m']
        require(left == right,
                'Selected fallback changed red-curb comparison: ' + case_id + '/' + candidate_id)
        require(candidate['trigger']['source'] and candidate['trigger']['metric'] and
                candidate['trigger']['failure_condition'] and
                config['risk_trigger'] != 'none',
                'Selected fallback physical trigger missing: ' + case_id + '/' + candidate_id)
        rows.append({'candidate_id': candidate_id,
                     'construction_sha256': candidate['construction_sha256'],
                     'changed_controls': sorted(changed),
                     'red_curb_target_relation_preserved': True})
    return {'case_id': case_id, 'primary_construction_sha256': entry['construction_sha256'],
            'fallbacks': rows}


def audit(override=None):
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    cases = manifest['cases']
    require(len(cases) == 30 and len({row['case_id'] for row in cases}) == 30,
            'Selected case inventory differs')
    rows = [inspect_case(entry, override) for entry in cases]
    return {'format': 'c150142-current-candidate-isolation-v1',
            'passed': True, 'manifest_sha256': sha(manifest_path),
            'selected_cases': len(rows),
            'fallbacks_checked': sum(len(row['fallbacks']) for row in rows),
            'rows': rows, 'source_kind': 'authored_controller_request',
            'original_native_observed': False,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2, sort_keys=True))
