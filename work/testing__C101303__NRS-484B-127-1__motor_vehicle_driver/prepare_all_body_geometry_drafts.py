"""Build a coordinated, unselected 32-construction Native spacing draft."""
import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OLD = "target_center_spacing_m=config['requested_engineering_gap_m']+4"
NEW = ("target_center_spacing_m=config['requested_engineering_gap_m']+native_body_offset(\n"
       "                     ego,lead,context['following_forward_xy'])")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_one(row, label, helper, draft):
    source = ROOT / row['construction']
    if digest(source) != row['construction_sha256']:
        raise ValueError('Selected construction hash changed: ' + str(source))
    bundle = json.loads(source.read_text())
    runners = [entry for entry in bundle['files'] if entry['path'] == 'runner.py']
    if len(runners) != 1 or runners[0]['content'].count(OLD) != 1:
        raise ValueError('Expected one reviewed calibration: ' + str(source))
    runner = runners[0]
    import_line = 'from following_controller import FollowingController'
    if runner['content'].count(import_line) != 1:
        raise ValueError('Expected controller import: ' + str(source))
    runner['content'] = runner['content'].replace(
        import_line, import_line + '\nfrom body_gap_geometry import native_body_offset', 1
    ).replace(OLD, NEW, 1)
    if any(entry['path'] == 'body_gap_geometry.py' for entry in bundle['files']):
        raise ValueError('Helper already bundled: ' + str(source))
    bundle['files'].append({'path': 'body_gap_geometry.py', 'content': helper})
    target = draft / (label + '.json')
    target.write_text(json.dumps(bundle, indent=2) + '\n')
    row['construction'] = str(target.relative_to(ROOT))
    row['construction_sha256'] = digest(target)
    # Existing receipts describe selected constructions. A draft cannot inherit
    # those proof claims; it must be re-proved before selection.
    row.pop('offline', None)
    row.pop('compatibility', None)
    return target


def main():
    original = json.loads((ROOT / 'execution-manifest.json').read_text())
    manifest = copy.deepcopy(original)
    helper_path = ROOT / 'body_gap_geometry.py'
    helper = helper_path.read_text()
    draft = ROOT / 'body-geometry-draft' / 'all'
    draft.mkdir(parents=True, exist_ok=True)
    built = []
    for case in manifest['cases']:
        suffix = case['case_id'].rsplit('__', 1)[-1]
        built.append(build_one(case, suffix + '-primary', helper, draft))
        for candidate in case['candidates']:
            built.append(build_one(candidate, suffix + '-' + candidate['id'], helper, draft))
    if len(built) != 32:
        raise ValueError('Expected eight selected cases and 24 fallbacks')
    output = ROOT / 'body-geometry-all-draft-manifest.json'
    output.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'construction_count': len(built), 'manifest': str(output),
                      'manifest_sha256': digest(output), 'helper_sha256': digest(helper_path),
                      'selected_manifest_sha256': digest(ROOT / 'execution-manifest.json')},
                     sort_keys=True))


if __name__ == '__main__':
    main()
