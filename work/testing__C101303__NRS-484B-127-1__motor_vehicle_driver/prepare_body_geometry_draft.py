"""Materialize one exact construction draft for measured Native body spacing.

This deliberately leaves the selected manifest untouched until every linked
case and fallback can be rebuilt and re-proved with the same calibration.
"""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
CASE = 'testing__C101303__NRS-484B-127-1__motor_vehicle_driver__source_verified_closer'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = FOLDER / 'cases/source_verified_closer/construction.json'
    bundle = json.loads(source.read_text())
    if bundle['case_id'] != CASE:
        raise ValueError('Exact closer case required')
    runner = next(row for row in bundle['files'] if row['path'] == 'runner.py')
    old = "target_center_spacing_m=config['requested_engineering_gap_m']+4"
    if runner['content'].count(old) != 1 or 'from following_controller import FollowingController' not in runner['content']:
        raise ValueError('Reviewed runner calibration changed')
    runner['content'] = runner['content'].replace(
        'from following_controller import FollowingController',
        'from following_controller import FollowingController\nfrom body_gap_geometry import native_body_offset', 1)
    runner['content'] = runner['content'].replace(
        old, "target_center_spacing_m=config['requested_engineering_gap_m']+native_body_offset(\n"
             "                     ego,lead,context['following_forward_xy'])", 1)
    if any(row['path'] == 'body_gap_geometry.py' for row in bundle['files']):
        raise ValueError('Body geometry helper already bundled')
    bundle['files'].append({'path': 'body_gap_geometry.py',
                            'content': (FOLDER / 'body_gap_geometry.py').read_text()})
    draft = FOLDER / 'body-geometry-draft'
    draft.mkdir(exist_ok=True)
    construction = draft / 'closer-construction.json'
    construction.write_text(json.dumps(bundle, indent=2) + '\n')
    original = json.loads((FOLDER / 'execution-manifest.json').read_text())
    entry = next(item for item in original['cases'] if item['case_id'] == CASE)
    entry['construction'] = 'closer-construction.json'
    entry['construction_sha256'] = sha(construction)
    entry['candidates'] = []
    entry['candidate_risk'] = {'status': 'none',
                               'reason': 'Isolated primary offline construction draft only'}
    manifest = dict(original)
    manifest['cases'] = [entry]
    (draft / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'construction': str(construction),
                      'construction_sha256': sha(construction),
                      'helper_sha256': sha(FOLDER / 'body_gap_geometry.py'),
                      'selected_manifest_changed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
