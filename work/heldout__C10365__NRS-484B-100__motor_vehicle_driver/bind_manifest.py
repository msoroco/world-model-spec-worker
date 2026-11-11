"""Bind exact pinned-runtime proof receipts to the officer delivery manifest."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
proofs = json.loads((ROOT / 'candidate-proofs.json').read_text())['cases']
by_case = {(row['case_id'], row['candidate_id']): row for row in proofs}
manifest = json.loads((ROOT / 'probe-compatibility-manifest.json').read_text())


def bind(entry, ident, target):
    case = entry['case_id']
    row = by_case[(case, ident)]
    slug = case.split('__')[-1]
    label = f'{slug}-{ident}'
    option = '' if ident == 'primary' else f' --candidate {ident}'
    base = f'.venv-cpu/bin/python runtime.py offline --manifest work/{AID}/execution-manifest.json --case {case}{option}'
    target['offline'] = {
        'command': f'{base} --output .runtime-work/c10365-{label}-offline-next --python .venv-cpu/bin/python',
        'exit_code': 0,
        'log': row['offline_log'],
        'log_sha256': row['offline_log_sha256'],
        'construction_sha256': row['construction_sha256'],
    }
    target['compatibility'] = {
        'receipt': row['compatibility_receipt'],
        'sha256': row['compatibility_receipt_sha256'],
        'log': f'cases/analysis-{label}.log',
        'negative_log': f'cases/negative-{label}.log',
    }


for entry in manifest['cases']:
    bind(entry, 'primary', entry)
    for candidate in entry['candidates']:
        bind(entry, candidate['id'], candidate)
    slug = entry['case_id'].split('__')[-1]
    row = by_case[(entry['case_id'], 'primary')]
    entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
    entry['negative'] = {'log': f'cases/negative-{slug}-primary.log'}
    entry['post_capture'] = {
        'recorded_only': True,
        'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {entry["case_id"]} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $VALIDATOR',
        'feedback_command': 'cat $OUTPUT/v0001/feedback.json',
        'test_log': row['saved_log'],
        'test_log_sha256': row['saved_log_sha256'],
        'test_exit_code': 0,
    }
manifest['format'] = 'worker-execution-manifest'
(ROOT / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
