"""Build reviewable, unselected current-runtime entries for survey pairs."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
ROOT = ASSIGNMENT.parents[1]
BASE = ASSIGNMENT.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def proof_path(code, label, candidate, name):
    folder = f'crossref-{code}-native/{label}' if candidate == 'primary' else f'crossref-{code}-fallback1/{label}'
    return f'{folder}/proofs/{name}'


def main():
    selected = read(ASSIGNMENT / 'execution-manifest.json')
    template = selected['cases'][0]
    physical = {x['case_id']: x for x in read(HERE / 'physical-proof-index.json')['cases']}
    delivery = {x['case_id']: x for x in read(HERE / 'delivery-proof-index.json')['cases']}
    entries = []
    for code in ('060a', '060b', '140b', '46'):
        manifest_path = ASSIGNMENT / f'crossref-{code}-manifest.json'
        manifest = read(manifest_path)
        for source in manifest['cases']:
            case = source['case_id']
            label = Path(source['construction']).parent.name
            record = delivery[case]
            entry = copy.deepcopy(template)
            for key in ('case_id', 'construction', 'construction_sha256',
                        'measurement_contract', 'measurement_procedure',
                        'fixture_recipe', 'candidate_risk'):
                entry[key] = source[key]
            entry['physical_preparation'] = physical[case]
            offline_log = proof_path(code, label, 'primary', 'offline.log')
            if not (ASSIGNMENT / offline_log).is_file():
                offline_log = f'crossref-{code}-native/{label}/offline.log'
            entry['offline'] = {
                'command': f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/{BASE}/crossref-{code}-manifest.json --case {case} --output .runtime-work/c230222-crossref-{code}-{label}-offline1',
                'exit_code': 0, 'construction_sha256': source['construction_sha256'],
                'log': offline_log, 'log_sha256': sha(ASSIGNMENT / offline_log)}
            positive_log = proof_path(code, label, 'primary', 'positive-analysis.log')
            negative_log = proof_path(code, label, 'primary', 'negative-analysis.log')
            compat = proof_path(code, label, 'primary', 'compatibility.json')
            processing_name = 'process-saved-processing.json' if code == '060a' else 'processing.json'
            saved = proof_path(code, label, 'primary', processing_name)
            entry['compatibility'] = {
                'receipt': compat, 'sha256': sha(ASSIGNMENT / compat),
                'log': positive_log, 'negative_log': negative_log}
            entry['negative'] = {'log': negative_log}
            entry['saved_processing'] = {'receipt': saved, 'sha256': sha(ASSIGNMENT / saved)}
            entry['post_capture'] = {
                'recorded_only': True,
                'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{BASE}/execution-manifest.json --case {case} --attempt "$ATTEMPT" --output "$OUTPUT" --library runtime/library --validator "$VALIDATOR"',
                'feedback_command': 'cat "$OUTPUT"/v0001/feedback.json',
                'test_log': saved, 'test_log_sha256': entry['saved_processing']['sha256'],
                'test_exit_code': 0}
            entry['candidates'] = [copy.deepcopy(source['candidates'][0])]
            fallback = entry['candidates'][0]
            fall_offline = proof_path(code, label, 'fallback1', 'offline.log')
            fall_compat = proof_path(code, label, 'fallback1', 'compatibility.json')
            fallback['offline'] = {
                'command': f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/{BASE}/crossref-{code}-manifest.json --case {case} --candidate fallback1 --output .runtime-work/c230222-crossref-{code}-{label}-fallback1-offline1',
                'exit_code': 0, 'construction_sha256': fallback['construction_sha256'],
                'log': fall_offline, 'log_sha256': sha(ASSIGNMENT / fall_offline)}
            fallback['compatibility'] = {
                'receipt': fall_compat, 'sha256': sha(ASSIGNMENT / fall_compat),
                'log': proof_path(code, label, 'fallback1', 'positive-analysis.log'),
                'negative_log': proof_path(code, label, 'fallback1', 'negative-analysis.log')}
            controls = {x['kind']: x for x in record['controls']}
            script = 'crossref-survey/delivery_audit.py'
            entry['delivery_acceptance'] = {
                'case_id': case, 'sets': ['full-train'],
                'checks': ['native_source', 'all_participants', 'time_join',
                           'full_video_decode', 'actual_pixels', 'physical_completion'],
                'script': script, 'script_sha256': sha(ASSIGNMENT / script),
                'command': controls['positive']['command'],
                'test_exit_code': 0, 'test_log': controls['positive']['log'],
                'test_log_sha256': controls['positive']['log_sha256'],
                'negative_command': controls['negative']['command'],
                'negative_exit_code': 1,
                'negative_expected_error': 'Original Native source required',
                'negative_log': controls['negative']['log'],
                'negative_log_sha256': controls['negative']['log_sha256'],
                'proof_scope': 'Synthetic software positive and original Native rejection; no physical acceptance'}
            entries.append(entry)
    draft = {'format': 'c230222-survey-delivery-entry-draft-v1',
             'assignment_id': BASE, 'selected': False,
             'runtime_manifest_sha256': selected['runtime_manifest_sha256'],
             'cases': entries}
    target = HERE / 'delivery-entry-draft.json'
    target.write_text(json.dumps(draft, indent=2) + '\n')
    print(json.dumps({'draft_entries': len(entries), 'sha256': sha(target)}))


if __name__ == '__main__':
    main()
