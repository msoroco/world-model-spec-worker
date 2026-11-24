"""Verify current long primary saved receipts and return compact bound logs."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    selected = {e['case_id']: e for e in manifest['cases']}
    summary_paths = sorted(HERE.glob('current-*-primary-saved-summary.json'))
    require(len(summary_paths) == 16, 'Long primary summary coverage incomplete')
    rows = []
    for summary_path in summary_paths:
        summary = json.loads(summary_path.read_text())
        case = summary['case_id']
        entry = selected.get(case)
        require(entry is not None and summary['candidate_id'] == 'primary' and
                summary['passed'] is True and summary['original_native_observed'] is False and
                summary['physical_acceptance_claimed'] is False and
                summary['legal_acceptance_claimed'] is False and
                summary['source_kind'] == 'synthetic_native_sample',
                'Long saved summary stale or overclaimed: ' + case)
        processing_path = REPO / summary['processing_ignored_path']
        log_path = REPO / summary['full_log_ignored_path']
        require(REPO / '.runtime-work' in processing_path.resolve().parents and
                REPO / '.runtime-work' in log_path.resolve().parents and
                sha(processing_path) == summary['processing_sha256'] and
                sha(log_path) == summary['full_log_sha256'],
                'Long saved scratch source hash differs: ' + case)
        processing = json.loads(processing_path.read_text())
        analysis = processing_path.parent / 'analysis'
        selection = json.loads((analysis / 'candidate-selection.json').read_text())
        require(selection['case_id'] == case and
                selection['candidate_id'] == 'primary' and
                selection['manifest_sha256'] == sha(manifest_path) and
                selection['construction_sha256'] == entry['construction_sha256'] and
                processing['case_id'] == case and
                processing['candidate_id'] == 'primary' and
                processing['passed'] is True and
                processing['recorded_only'] is True and
                processing['originals_preserved'] is True and
                processing['missing_evidence'] is False and
                processing['physical_acceptance_claimed'] is False and
                processing['legal_acceptance_claimed'] is False and
                processing['timestamp_joins']['frames'] == summary['frames'] and
                summary['final_decode_frames'] == summary['frames'] and
                summary['source_decodes'] == 4,
                'Long recorded-only or selection proof differs: ' + case)
        final_decode = processing_path.parent / 'final-decode.json'
        require(sha(final_decode) == summary['final_decode_sha256'],
                'Long final decode differs: ' + case)
        for index, expected in enumerate(summary['source_decode_sha256']):
            require(sha(processing_path.parent / ('source-' + str(index) + '.json')) == expected,
                    'Long source decode differs: ' + case)
        slug = case.rsplit('__', 1)[1]
        log = HERE / 'long-recorded-only-proofs' / (slug + '.log')
        write(log, {'format': 'c150142-long-recorded-only-cpu-proof-v1',
                    'case_id': case, 'passed': True, 'recorded_only': True,
                    'selected_manifest_sha256': sha(manifest_path),
                    'construction_sha256': entry['construction_sha256'],
                    'summary_sha256': sha(summary_path),
                    'full_process_log_sha256': sha(log_path),
                    'processing_sha256': sha(processing_path),
                    'source_decode_sha256': summary['source_decode_sha256'],
                    'final_decode_sha256': sha(final_decode),
                    'frames': summary['frames'],
                    'original_native_observed': False,
                    'physical_acceptance_claimed': False,
                    'legal_acceptance_claimed': False})
        rows.append({'case_id': case, 'test_log': str(log.relative_to(HERE)),
                     'test_log_sha256': sha(log), 'test_exit_code': 0,
                     'processing_sha256': sha(processing_path)})
    require(len({r['case_id'] for r in rows}) == 16,
            'Duplicate long saved case')
    index_path = HERE / 'current-long-recorded-only-cpu-index.json'
    write(index_path, {'format': 'c150142-long-recorded-only-cpu-index-v1',
                       'passed': True, 'cases': rows,
                       'selected_manifest_sha256': sha(manifest_path),
                       'source_kind': 'synthetic_native_sample',
                       'original_native_observed': False,
                       'physical_acceptance_claimed': False})
    return {'cases': len(rows), 'index_sha256': sha(index_path)}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
