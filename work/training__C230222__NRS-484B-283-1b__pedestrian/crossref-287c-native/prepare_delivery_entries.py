"""Build reviewable 287(c) delivery entries without selecting them yet."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
BASE = ASSIGNMENT.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def proof_path(label, candidate, name):
    return f'crossref-287c-native/{label}/' + ('proofs/' if candidate == 'primary' else 'fallback1/proofs/') + name


def main():
    selected = json.loads((ASSIGNMENT / 'execution-manifest.json').read_text())
    template = selected['cases'][0]
    source = json.loads((ASSIGNMENT / 'crossref-287c-manifest.json').read_text())
    physical = json.loads((HERE / 'physical-proof-index.json').read_text())
    entries = []
    for label, source_entry, physical_entry in zip(('marked', 'unmarked'), source['cases'], physical['cases']):
        entry = copy.deepcopy(template)
        case = BASE + '__crossref_287c_' + label
        if source_entry['case_id'] != case or physical_entry['case_id'] != case:
            raise ValueError('287(c) draft source identity differs')
        entry['case_id'] = case
        entry['construction'] = source_entry['construction']
        entry['construction_sha256'] = source_entry['construction_sha256']
        entry['measurement_contract'] = source_entry['measurement_contract']
        entry['measurement_procedure'] = source_entry['measurement_procedure']
        entry['fixture_recipe'] = source_entry['fixture_recipe']
        entry['candidate_risk'] = source_entry['candidate_risk']
        entry['offline'] = {
            'command': f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/{BASE}/crossref-287c-manifest.json --case {case} --output .runtime-work/c230222-287c-topology-{label}-offline2',
            'exit_code': 0, 'construction_sha256': entry['construction_sha256'],
            'log': proof_path(label, 'primary', 'offline.log'),
            'log_sha256': sha(ASSIGNMENT / proof_path(label, 'primary', 'offline.log'))}
        entry['compatibility'] = {
            'receipt': proof_path(label, 'primary', 'compatibility.json'),
            'sha256': sha(ASSIGNMENT / proof_path(label, 'primary', 'compatibility.json')),
            'log': proof_path(label, 'primary', 'positive-analysis.log'),
            'negative_log': proof_path(label, 'primary', 'negative-analysis.log')}
        entry['negative'] = {'log': proof_path(label, 'primary', 'negative-analysis.log')}
        entry['saved_processing'] = {
            'receipt': proof_path(label, 'primary', 'processing.json'),
            'sha256': sha(ASSIGNMENT / proof_path(label, 'primary', 'processing.json'))}
        entry['post_capture'] = {
            'recorded_only': True,
            'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{BASE}/execution-manifest.json --case {case} --attempt "$ATTEMPT" --output "$OUTPUT" --library runtime/library --validator "$VALIDATOR"',
            'feedback_command': 'cat "$OUTPUT"/v0001/feedback.json',
            'test_log': proof_path(label, 'primary', 'processing.json'),
            'test_log_sha256': entry['saved_processing']['sha256'],
            'test_exit_code': 0}
        entry['physical_preparation'] = {'case_id': case, 'receipt': physical_entry['receipt'],
                                         'sha256': physical_entry['sha256']}
        entry['candidates'] = [copy.deepcopy(source_entry['candidates'][0])]
        fallback = entry['candidates'][0]
        fallback['offline'] = {
            'command': f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/{BASE}/crossref-287c-manifest.json --case {case} --candidate fallback1 --output .runtime-work/c230222-287c-fallback-{label}-offline',
            'exit_code': 0, 'construction_sha256': fallback['construction_sha256'],
            'log': f'crossref-287c-native/{label}/fallback1/offline.log',
            'log_sha256': sha(ASSIGNMENT / f'crossref-287c-native/{label}/fallback1/offline.log')}
        fallback['compatibility'] = {
            'receipt': proof_path(label, 'fallback1', 'compatibility.json'),
            'sha256': sha(ASSIGNMENT / proof_path(label, 'fallback1', 'compatibility.json')),
            'log': proof_path(label, 'fallback1', 'positive-analysis.log'),
            'negative_log': proof_path(label, 'fallback1', 'negative-analysis.log')}
        script = 'crossref-287c-native/delivery_audit.py'
        folder = HERE / label / 'proofs'
        repo = ASSIGNMENT.parents[1]
        attempt = repo / '.runtime-work' / f'c230222-287c-topology-{label}-compat'
        processing = repo / '.runtime-work' / f'c230222-287c-topology-{label}-saved/v0001/processing.json'
        command = f'{repo}/.venv-cpu/bin/python {ASSIGNMENT / script} --case {case} --candidate primary --attempt {attempt} --processing {processing}'
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': script, 'script_sha256': sha(ASSIGNMENT / script),
            'command': command + f' --output {repo / ".runtime-work" / f"c230222-287c-topology-{label}-delivery-diagnostic.json"} --diagnostic',
            'test_exit_code': 0,
            'test_log': proof_path(label, 'primary', 'delivery-positive.log'),
            'test_log_sha256': sha(folder / 'delivery-positive.log'),
            'negative_command': command + f' --output {repo / ".runtime-work" / f"c230222-287c-topology-{label}-delivery-rejected.json"}',
            'negative_exit_code': 1,
            'negative_expected_error': 'Original Native source required',
            'negative_log': proof_path(label, 'primary', 'delivery-negative.log'),
            'negative_log_sha256': sha(folder / 'delivery-negative.log'),
            'proof_scope': 'Synthetic software positive and original Native rejection; no physical acceptance'}
        entries.append(entry)
    draft = {'format': 'c230222-287c-delivery-entry-draft-v1',
             'assignment_id': BASE, 'selected': False,
             'runtime_manifest_sha256': selected['runtime_manifest_sha256'],
             'cases': entries}
    target = HERE / 'delivery-entry-draft.json'
    target.write_text(json.dumps(draft, indent=2) + '\n')
    print(json.dumps({'draft_entries': len(entries), 'sha256': sha(target)}))


if __name__ == '__main__':
    main()
