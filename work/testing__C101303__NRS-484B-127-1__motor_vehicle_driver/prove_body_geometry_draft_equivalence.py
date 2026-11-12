"""Prove the draft delta leaves source/camera/finalizer audit inputs intact."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OLD = "target_center_spacing_m=config['requested_engineering_gap_m']+4"
NEW = ("target_center_spacing_m=config['requested_engineering_gap_m']+native_body_offset(\n"
       "                     ego,lead,context['following_forward_xy'])")
IMPORT = 'from following_controller import FollowingController'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_map(bundle):
    result = {row['path']: row['content'] for row in bundle['files']}
    if len(result) != len(bundle['files']):
        raise ValueError('Duplicate construction file path')
    return result


def main():
    selected_path = (ROOT / 'body-geometry-draft/pre-promotion-execution-manifest.json'
                     if (ROOT / 'body-geometry-draft/pre-promotion-execution-manifest.json').exists()
                     else ROOT / 'execution-manifest.json')
    draft_path = ROOT / 'body-geometry-all-draft-manifest.json'
    selected = json.loads(selected_path.read_text())
    draft = json.loads(draft_path.read_text())
    if [row['case_id'] for row in selected['cases']] != [row['case_id'] for row in draft['cases']]:
        raise ValueError('Draft changed exact case inventory')
    helper = (ROOT / 'body_gap_geometry.py').read_text()
    rows = []
    for old_case, new_case in zip(selected['cases'], draft['cases']):
        old_rows = [old_case] + old_case['candidates']
        new_rows = [new_case] + new_case['candidates']
        if [row.get('id', 'primary') for row in old_rows] != [row.get('id', 'primary')
                                                               for row in new_rows]:
            raise ValueError('Draft changed candidate inventory')
        for old_row, new_row in zip(old_rows, new_rows):
            old_path = (ROOT / 'body-geometry-draft/pre-promotion-base-construction.json'
                        if old_row['construction'] == 'construction.json' and
                        (ROOT / 'body-geometry-draft/pre-promotion-base-construction.json').exists()
                        else ROOT / old_row['construction'])
            new_path = ROOT / new_row['construction']
            if (digest(old_path) != old_row['construction_sha256'] or
                    digest(new_path) != new_row['construction_sha256']):
                raise ValueError('Selected or draft construction hash changed')
            old_bundle, new_bundle = json.loads(old_path.read_text()), json.loads(new_path.read_text())
            original, changed = file_map(old_bundle), file_map(new_bundle)
            if (old_bundle['case_id'] != new_bundle['case_id'] or
                    set(changed) != set(original) | {'body_gap_geometry.py'} or
                    changed['body_gap_geometry.py'] != helper):
                raise ValueError('Draft changes more than expected inventory')
            runner = original['runner.py']
            if runner.count(OLD) != 1 or runner.count(IMPORT) != 1:
                raise ValueError('Selected runner calibration drifted')
            expected_runner = runner.replace(IMPORT, IMPORT + '\nfrom body_gap_geometry import native_body_offset', 1).replace(OLD, NEW, 1)
            if changed['runner.py'] != expected_runner:
                raise ValueError('Draft runner changes more than body spacing')
            for name in original.keys() - {'runner.py'}:
                if original[name] != changed[name]:
                    raise ValueError('Draft changed retained source or finalizer input: ' + name)
            rows.append({'case_id': old_bundle['case_id'],
                         'candidate_id': old_row.get('id', 'primary'),
                         'selected_sha256': old_row['construction_sha256'],
                         'draft_sha256': new_row['construction_sha256'],
                         'unchanged_file_count': len(original) - 1})
    if len(rows) != 32:
        raise ValueError('Expected 32 exact bundles')
    delivery = ROOT / 'delivery_audit.py'
    comparison = ROOT / 'comparison_audit.py'
    output = ROOT / 'body-geometry-draft/equivalence-proof.json'
    output.write_text(json.dumps({'selected_manifest_sha256': digest(selected_path),
                                  'draft_manifest_sha256': digest(draft_path),
                                  'helper_sha256': digest(ROOT / 'body_gap_geometry.py'),
                                  'delivery_audit_sha256': digest(delivery),
                                  'comparison_audit_sha256': digest(comparison),
                                  'only_runner_spacing_and_helper_changed': True,
                                  'bundle_count': len(rows), 'bundles': rows},
                                 indent=2) + '\n')
    print('exact bundles with source/finalizer identity:', len(rows))


if __name__ == '__main__':
    main()
