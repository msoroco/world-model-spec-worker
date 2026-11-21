"""Bind every selected C183370 candidate to current CPU diagnostic artifacts.

This verifies software paths only. It cannot establish original Native motion,
camera pixels, statutory facts, or physical acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LABELS = {
    'reference': 'update143', 'contrast': 'update143',
    'barrier_crossing': 'update144', 'barrier_avoidance': 'update144',
    'warning_sign_crossing': 'update145', 'warning_sign_avoidance': 'update145',
    'highway_closed_sign_crossing': 'update146',
    'highway_closed_sign_avoidance': 'update146',
    'employee_exception_employee_crossing': 'update147',
    'employee_exception_nonemployee_crossing': 'update147',
    'newly_laid_crossing': 'update142', 'newly_laid_avoidance': 'update142',
}
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(shorts):
    manifest_path = HERE / 'execution-manifest.json'
    manifest, manifest_sha = read(manifest_path), sha(manifest_path)
    entries = {row['case_id'].removeprefix(HERE.name + '__'): row
               for row in manifest['cases']}
    require(set(entries) == set(LABELS), 'Selected case inventory differs')
    selected = tuple(LABELS) if shorts is None else tuple(shorts)
    require(selected and len(set(selected)) == len(selected)
            and set(selected) <= set(entries), 'Requested case inventory differs')
    rows = []
    for short in selected:
        entry, label = entries[short], LABELS[short]
        require({row['id'] for row in entry['candidates']} == set(CANDIDATES[1:]),
                'Fallback inventory differs: ' + short)
        for candidate in CANDIDATES:
            name = f'{label}-{short}-{candidate}'
            proof_path = HERE / (name + '-proof.json')
            proof = read(proof_path)
            construction = (entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate))
            require(proof['case_id'] == entry['case_id']
                    and proof['candidate_id'] == candidate
                    and proof['manifest_sha256'] == manifest_sha
                    and proof['construction_sha256'] == construction['construction_sha256'],
                    'Exact selected binding differs: ' + name)
            require(proof['synthetic_fixture'] is True
                    and proof['diagnostic_delivery_accepted'] is False
                    and proof['original_native_verified'] is False,
                    'Diagnostic was promoted: ' + name)
            require(set(proof['logs']) == {'offline', 'compat', 'stage', 'saved'},
                    'Proof log inventory differs: ' + name)
            for kind, digest in proof['logs'].items():
                require(sha(HERE / (name + '-' + kind + '.log')) == digest,
                        'Proof log hash differs: ' + name + '/' + kind)
            base = ROOT / '.runtime-work' / ('c183370-' + name)
            artifacts = {
                'offline_selection_sha256': Path(str(base) + '-offline/candidate-selection.json'),
                'compatibility_sha256': Path(str(base) + '-compat/compatibility.json'),
                'saved_sha256': Path(str(base) + '-saved/v0001/processing.json'),
            }
            for key, path in artifacts.items():
                require(sha(path) == proof[key],
                        'Diagnostic artifact hash differs: ' + name + '/' + key)
            offline = read(artifacts['offline_selection_sha256'])
            compatible = read(artifacts['compatibility_sha256'])
            processing = read(artifacts['saved_sha256'])
            source = Path(str(base) + '-source')
            source_selection = read(source / 'candidate-selection.json')
            require(offline['manifest_sha256'] == source_selection['manifest_sha256'] ==
                    manifest_sha and offline['case_id'] == source_selection['case_id'] ==
                    entry['case_id'] and offline['candidate_id'] ==
                    source_selection['candidate_id'] == candidate,
                    'Offline/source selection differs: ' + name)
            require(compatible['passed'] is True and
                    compatible['case_id'] == entry['case_id'] and
                    compatible['candidate_id'] == candidate and
                    compatible['construction_sha256'] == construction['construction_sha256'],
                    'Compatibility differs: ' + name)
            require(processing['passed'] is True
                    and processing['recorded_only'] is True
                    and processing['originals_preserved'] is True
                    and processing['timestamp_joins']['passed'] is True
                    and processing['timestamp_joins']['frames'] == 600
                    and processing['final_video_checks']['passed'] is True
                    and processing['final_video_checks']['frames'] == 600
                    and processing['analysis_revision']['construction_sha256'] ==
                    construction['construction_sha256'],
                    'Saved processing differs: ' + name)
            for camera in CAMERAS:
                require(sha(source / camera) ==
                        processing['original_source_hashes'][camera],
                        'Four-view source differs: ' + name + '/' + camera)
            rows.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                         'proof_path': proof_path.name, 'proof_sha256': sha(proof_path),
                         'saved_sha256': proof['saved_sha256']})
    return {'format': 'c183370-current-selected-cpu-diagnostic-matrix-v1',
            'assignment_id': HERE.name, 'manifest_sha256': manifest_sha,
            'selected_case_count': len(selected), 'candidate_count': len(rows),
            'proofs': rows, 'diagnostic_only': True,
            'original_native_verified': False, 'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-suffix', action='append')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.case_suffix)
    require(not args.output.exists(), 'Retain previous selected matrix')
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'cases': result['selected_case_count'],
                      'candidates': result['candidate_count'],
                      'matrix_sha256': sha(args.output)}, sort_keys=True))
