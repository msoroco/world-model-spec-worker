"""Bind exact selected draft constructions and CPU receipts without asserting readiness."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
NATIVE = ROOT / 'native'
ASSIGNMENT = ROOT.name
GROUPS = (
    ('selected-paragraph-d', 'preview-execution-manifest.json'),
    ('exception-1', 'preview-exception-1-manifest.json'),
    ('current-c1', 'preview-current-c1-manifest.json'),
    ('exception-4', 'preview-exception-4-manifest.json'),
    ('subsection-4', 'preview-subsection4-manifest.json'),
    ('numeric-boundary', 'preview-numeric-manifest.json'),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return str(path.relative_to(ROOT))


def offline_source(group, suffix):
    if group == 'selected-paragraph-d':
        return NATIVE / group / (suffix + '-offline-refresh.log')
    if group == 'exception-1':
        return NATIVE / group / (suffix + '-offline-refresh.log')
    if group == 'exception-4':
        return NATIVE / group / (suffix + '-offline.log')
    prefix = {'current-c1': 'current-c1-offline-v2-',
              'subsection-4': 'sub4-offline-',
              'numeric-boundary': 'numeric-offline-'}[group]
    source = REPO / '.runtime-work/c146314-210-1' / (prefix + suffix) / 'offline.log'
    target = NATIVE / group / (suffix + '-selected-offline.log')
    if not target.exists():
        target.write_text(source.read_text().rstrip() + '\n')
    return target


def main():
    entries = []
    runtime_sha = sha(REPO / 'runtime/SOURCE-MANIFEST.json')
    for group, preview_name in GROUPS:
        preview = json.loads((ROOT / preview_name).read_text())
        assert preview['runtime_manifest_sha256'] == runtime_sha
        for source_entry in preview['cases']:
            entry = dict(source_entry)
            suffix = entry['case_id'].split('__')[-1]
            construction = ROOT / entry['construction']
            assert entry['construction_sha256'] == sha(construction)
            case_dir = NATIVE / group / suffix
            receipt = case_dir / 'compatibility.json'
            saved = case_dir / 'saved-processing.json'
            log = case_dir / 'public-analysis.log'
            negative = case_dir / 'negative-analysis.log'
            proof = json.loads(receipt.read_text())
            assert proof['passed'] is True
            assert proof['construction_sha256'] == sha(construction)
            assert proof['log_sha256'] == sha(log)
            assert proof['negative_log_sha256'] == sha(negative)
            assert json.loads(saved.read_text())['recorded_only'] is True
            offline = offline_source(group, suffix)
            entry['offline'] = {'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + ASSIGNMENT + '/' + preview_name + ' --case ' + entry['case_id'] + ' --output .runtime-work/c146314-210-1/' + group + '-' + suffix,
                                'construction_sha256': sha(construction),
                                'exit_code': 0, 'log': relative(offline),
                                'log_sha256': sha(offline)}
            entry['compatibility'] = {'receipt': relative(receipt),
                                      'sha256': sha(receipt),
                                      'log': relative(log),
                                      'negative_log': relative(negative)}
            entry['negative'] = {'log': relative(negative)}
            entry['post_capture'] = {'recorded_only': True,
                                     'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + ASSIGNMENT + '/' + preview_name + ' --case ' + entry['case_id'] + ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library --validator "$DECODER"',
                                     'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
                                     'test_exit_code': 0,
                                     'test_log': relative(saved),
                                     'test_log_sha256': sha(saved)}
            entry['delivery_acceptance_cpu'] = {
                'audit_script': 'delivery_audit.py',
                'audit_script_sha256': sha(ROOT / 'delivery_audit.py'),
                'selftest_log': 'native/delivery-cpu/' + suffix + '-positive.log',
                'negative_log': 'native/delivery-cpu/' + suffix + '-negative.log',
                'original_native_accepted': False}
            if group == 'current-c1' and suffix == 'exception_3_1':
                path = NATIVE / 'physical-fixtures/proof.json'
                entry['physical_preparation_cpu'] = {'receipt': relative(path),
                                                     'sha256': sha(path)}
            entry['remaining_cpu_bindings'] = ['risk_fallbacks',
                                                'per_case_physical_preparation',
                                                'delivery_acceptance_positive_and_negative',
                                                'independent_physical_comparison']
            entries.append(entry)
    selected = {case['case_id'] for case in json.loads((ROOT / 'proposals/cases.json').read_text())['cases']
                if case['target_type'] != 'baseline'}
    assert len(entries) == len(selected) == 13
    assert {entry['case_id'] for entry in entries} == selected
    document = {'format': 'worker-execution-manifest',
                'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': runtime_sha,
                'status': 'selected_cpu_draft_partial',
                'delivery_ready': False,
                'original_native_observed': False,
                'source_law_sha256': '9241d1e338fc52dc9d744182b1535b92bfd064b3be00ddac896b70189ba0bd31',
                'paragraph_b_binding': None,
                'paragraph_b_binding_proof_sha256': sha(NATIVE / 'paragraph-b-binding-proof.json'),
                'selected_semantic_index_sha256': sha(ROOT / 'proposals/semantic-index.json'),
                'selected_comparison_cpu_sha256': sha(NATIVE / 'selected-comparison-cpu-audit.json'),
                'cases': entries}
    path = ROOT / 'draft-selected-execution-manifest.json'
    path.write_text(json.dumps(document, indent=2, allow_nan=False) + '\n')
    print('BUILT', len(entries), 'selected case draft bindings; paragraph (b) remains unbound')


if __name__ == '__main__':
    main()
