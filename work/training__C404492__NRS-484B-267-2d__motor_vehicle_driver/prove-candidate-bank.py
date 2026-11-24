"""Check candidate engineering changes against source-shaped Native survey inputs."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_runner(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def survey(gap, cameras):
    return {
        'map_name': 'reviewed_test_map', 'map_source': 'source:map',
        'lane_boundaries_source': 'source:lanes',
        'emergency_authorization_source': 'source:authorization',
        'qualifying_flash_equipment_source': 'source:equipment',
        'officer_direction_review_source': 'source:officer',
        'ego_blueprint': 'vehicle.ego', 'emergency_blueprint': 'vehicle.emergency',
        'ego_spawn_xyz_m': [gap, 0, 0], 'emergency_spawn_xyz_m': [0, 3.5, 0],
        'camera_world_transforms': {name: {'xyz_m': [0, 0, 3], 'rotation_deg': [0, 0, 0]}
                                    for name in cameras},
        'emergency_vehicle_authorized': True,
        'qualifying_flash_equipment_reviewed': True,
        'officer_directed_otherwise': False,
    }


def rejected(call):
    try:
        call()
    except ValueError:
        return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    root = here.parents[1]
    scratch = args.scratch.resolve()
    if root / '.runtime-work' not in scratch.parents:
        raise ValueError('Scratch must be under .runtime-work')
    scratch.mkdir(parents=True, exist_ok=True)
    manifest = here / 'draft-emergency-manifest.json'
    entries = json.loads(manifest.read_text())['cases']
    expected = {'primary': (-20, 0, 90), 'fallback1': (-25, 0, 90),
                'fallback2': (-20, 1.0, 105)}
    rows = []
    for entry in entries:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate, (gap, height, fov) in expected.items():
            construction_path = here / ('draft-emergency/' + suffix + '/' + candidate + '/construction.json')
            construction = json.loads(construction_path.read_text())
            with tempfile.TemporaryDirectory(prefix='survey-', dir=scratch) as tmp:
                materialized = Path(tmp)
                for file in construction['files']:
                    target = materialized / file['path']
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(file['content'])
                runner = load_runner(materialized / 'runner.py', suffix + '_' + candidate)
                cfg = runner.config()
                if (cfg['engineering_initial_ego_gap_m'], cfg['camera_height_offset_m'],
                        cfg['camera_fov_deg']) != (gap, height, fov):
                    raise ValueError('Candidate engineering knobs differ')
                good = survey(gap, runner.CAMERAS)
                runner.survey_check(good)
                changed_gap = survey(gap + 2, runner.CAMERAS)
                missing_authorization = survey(gap, runner.CAMERAS)
                missing_authorization['emergency_vehicle_authorized'] = False
                missing_camera = survey(gap, runner.CAMERAS)
                del missing_camera['camera_world_transforms']['rear']
                negatives = [rejected(lambda x=x: runner.survey_check(x)) for x in
                             (changed_gap, missing_authorization, missing_camera)]
                if negatives != [True, True, True]:
                    raise ValueError('Candidate survey negative escaped')
            rows.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                         'construction_sha256': sha(construction_path),
                         'survey_positive': True, 'changed_gap_rejected': True,
                         'missing_authorization_rejected': True,
                         'missing_camera_rejected': True,
                         'candidate_knobs': [gap, height, fov]})
    print(json.dumps({'format': 'c404492-candidate-bank-survey-proof',
                      'manifest_sha256': sha(manifest), 'cases': rows,
                      'original_native_executed': False, 'passed': True}, indent=2))


if __name__ == '__main__':
    main()
