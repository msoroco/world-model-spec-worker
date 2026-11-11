"""Independent current four-camera and U-turn offline proof audit."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NATIVE = HERE / 'native'
sys.path.insert(0, str(NATIVE))
from capture import camera_specs as intersection_cameras
from capture_divided import camera_specs as divided_cameras
from check import check as intersection_check
from divided_opening import check as divided_check, measure as divided_measure
from process_original import CAMERAS, CAMERA_SIZES
from prove_original_processing import prove as intersection_prove
from prove_original_divided import prove as divided_prove


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit():
    matrix = json.loads((HERE / 'update015-offline-proof-matrix.json').read_text())
    require(len(matrix['bundles']) == 16, 'Missing candidate bundle')
    expected = [('overview', 1920, 1080), ('approach', 1280, 720),
                ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]
    require(list(CAMERAS) == [row[0] for row in expected] and
            [CAMERA_SIZES[name] for name in CAMERAS] ==
            [(width, height) for _, width, height in expected],
            'Original saved media contract differs from four cameras')
    for plan in (intersection_cameras, divided_cameras):
        for policy, overview_height in (('standard', 38), ('elevated_overview', 55)):
            specs = plan(policy)
            require([(row[0], row[1], row[2]) for row in specs] == expected and
                    specs[0][3][2] == overview_height,
                    'Capture camera profile differs')
        try:
            plan('unknown')
        except ValueError:
            pass
        else:
            raise ValueError('Unknown camera policy accepted')
    positive = negative = 0
    pairs = {}
    for branch, manifest_path, cases, base, check, prove in (
            ('intersection', NATIVE / 'draft-execution-manifest.json',
             ('reference', 'contrast'), NATIVE / 'drafts',
             intersection_check, intersection_prove),
            ('divided', NATIVE / 'divided-opening/draft-execution-manifest.json',
             ('divided_reference', 'divided_opening'),
             NATIVE / 'divided-opening/drafts', divided_check, divided_prove)):
        manifest = json.loads(manifest_path.read_text())
        require(len(manifest['cases']) == 2, 'Branch case count differs')
        pairs[branch] = {}
        for case in cases:
            entry = next(item for item in manifest['cases']
                         if item['case_id'] == HERE.name + '__' + case)
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                row = next(item for item in matrix['bundles']
                           if item['branch'] == branch and
                           item['case_id'] == entry['case_id'] and
                           item['candidate_id'] == candidate)
                selected = entry if candidate == 'primary' else next(
                    item for item in entry['candidates'] if item['id'] == candidate)
                construction = manifest_path.parent / selected['construction']
                require(sha(construction) == selected['construction_sha256'] ==
                        row['construction_sha256'], 'Construction source changed')
                for key, hash_key in (('command_log', 'command_log_sha256'),
                                      ('offline_log', 'offline_log_sha256')):
                    require(sha(HERE / row[key]) == row[hash_key],
                            'Offline proof log changed')
                require(row['exit_code'] == 0 and row['offline_passed'] and
                        'Ran 5 tests' in (HERE / row['offline_log']).read_text() and
                        (HERE / row['offline_log']).read_text().rstrip().endswith('OK'),
                        'Current offline tests incomplete')
                bundle = base / case / candidate
                require(check(bundle)['frames'] == 800, 'Exact authored request differs')
                cfg = json.loads((bundle / 'config.json').read_text())
                pairs[branch].setdefault(candidate, {})[case] = cfg
                proof = prove(bundle)
                require(proof['positive_count'] == 1 and
                        proof['negative_count'] == 7 and
                        proof['original_native_observed'] is False and
                        proof['delivery_ready'] is False,
                        'Original source-shape proof differs')
                if branch == 'divided':
                    require(divided_measure(bundle)['original_native_observed'] is False,
                            'Divided synthetic measure changed provenance')
                positive += 1
                negative += proof['negative_count']
        for candidate, values in pairs[branch].items():
            left, right = (values[case] for case in cases)
            changes = {key for key in left if left[key] != right.get(key)}
            require(changes == {'case_id', 'requested_turn_center_x_m',
                                'tracks_sha256'} and
                    left['requested_turn_center_x_m'] == -45.0 and
                    right['requested_turn_center_x_m'] == 0.0,
                    'Controlled U-turn pair changed additional conditions')
    return {'format': 'c111662-update015-four-camera-independent-audit-v1',
            'passed': True, 'bundle_count': 16, 'offline_tests': 80,
            'source_shape_positives': positive, 'source_shape_negatives': negative,
            'controlled_pairs': 8, 'four_cameras': expected,
            'physical_native_or_business_district_verified': False,
            'matrix_sha256': sha(HERE / 'update015-offline-proof-matrix.json')}


if __name__ == '__main__':
    result = audit()
    (HERE / 'update015-offline-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))
