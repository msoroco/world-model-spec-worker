"""Bind exact bicycle delivery intent to source-labeled diagnostic CPU receipts."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / '.runtime-work/c143687-nov25a'
ASSIGNMENT = HERE.name
NAMES = ('posted_enter', 'posted_stop', 'posted_remain_trail')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def main() -> None:
    diagnostic = json.loads((HERE / 'diagnostic-execution-manifest.json').read_text())
    entries = []
    for source in diagnostic['cases']:
        case_id = source['case_id']
        suffix = case_id.removeprefix(ASSIGNMENT + '__')
        if suffix not in NAMES:
            raise ValueError('nonselected bicycle case')
        folder = HERE / 'cases' / suffix
        origin = SCRATCH / ('v2-compat-' + suffix)
        for name, path in {
            'compatibility.json': origin / 'compatibility.json',
            'cpu-compat-analysis.log': origin / 'compatibility-analysis.log',
            'negative-analysis.log': origin / 'negative-analysis.log',
            'offline.log': SCRATCH / ('v2-offline-' + suffix) / 'offline.log',
        }.items():
            copy(path, folder / name)
        saved = HERE / ('cpu-pinned-saved-' + suffix + '.json')
        copy(SCRATCH / ('v2-saved-' + suffix + '.json'), saved)
        entry = json.loads(json.dumps(source))
        construction_sha = entry['construction_sha256']
        physics = folder / 'physical-preparation.json'
        script = HERE / 'prove_delivery_contract.py'
        command = f'.venv-cpu/bin/python work/{ASSIGNMENT}/prove_delivery_contract.py --case {case_id}'
        entry.update(kind='delivery', status='source_gated_cpu_preparation',
                     offline={'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/diagnostic-execution-manifest.json --case {case_id} --output .runtime-work/c143687-nov25a/v2-offline-{suffix} --python $PWD/.venv-cpu/bin/python',
                              'exit_code': 0, 'log': f'cases/{suffix}/offline.log',
                              'log_sha256': sha(folder / 'offline.log'),
                              'construction_sha256': construction_sha},
                     physical_preparation={'receipt': f'cases/{suffix}/physical-preparation.json',
                                           'sha256': sha(physics)},
                     compatibility={'receipt': f'cases/{suffix}/compatibility.json',
                                    'sha256': sha(folder / 'compatibility.json'),
                                    'log': f'cases/{suffix}/cpu-compat-analysis.log'},
                     negative={'log': f'cases/{suffix}/negative-analysis.log'},
                     delivery_acceptance={
                         'case_id': case_id, 'sets': ['full-test'],
                         'checks': ['native_source', 'all_participants', 'time_join',
                                    'full_video_decode', 'actual_pixels', 'physical_completion'],
                         'scope': 'synthetic protocol CPU proof; original delivery pending',
                         'diagnostic_fixture': True,
                         'command': command + ' --mode diagnostic-positive',
                         'test_exit_code': 0,
                         'test_log': f'cases/{suffix}/delivery-positive.log',
                         'test_log_sha256': sha(folder / 'delivery-positive.log'),
                         'negative_command': command + ' --mode delivery-negative',
                         'negative_exit_code': 1,
                         'negative_expected_error': 'successful released original Native attempt required',
                         'negative_log': f'cases/{suffix}/delivery-negative.log',
                         'negative_log_sha256': sha(folder / 'delivery-negative.log'),
                         'script': 'prove_delivery_contract.py',
                         'script_sha256': sha(script)},
                     post_capture={
                         'recorded_only': True,
                         'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case_id} --attempt $ATTEMPT --output $DERIVED --library runtime/library --validator $VALIDATOR',
                         'feedback_command': f'.venv-cpu/bin/python work/{ASSIGNMENT}/delivery_audit.py --authority-root $SOURCE_ROOT --receipt $RECEIPT --output $AUDIT',
                         'test_exit_code': 0, 'test_log': saved.name,
                         'test_log_sha256': sha(saved)},
                     native_handoff={'python_env_var': 'CARLA_PYTHON',
                                     'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                     pending_original_sources=['reviewed City Traffic Engineer designation and original governed street',
                                               'erected sign wording, orientation, placement and applicability',
                                               'connected trail-to-roadway route and qualifying bicycle',
                                               'released Native four-camera selected attempts'])
        construction = json.loads((HERE / source['construction']).read_text())
        channels = {item['name'] for item in construction['recording_description']['channels']}
        entry['acquisition'] = {name: {'entrypoint': 'native_adapter.py', 'method': 'capture',
                                       'evidence': 'source-gated original Native sign/route/bicycle/camera readback'}
                                for name in sorted(channels)}
        for candidate in entry['candidates']:
            if candidate['id'] != 'fallback1' or suffix != 'posted_enter':
                raise ValueError('unexpected bicycle fallback')
            other = SCRATCH / 'v2-compat-fallback1'
            for name, path in {
                'fallback1-compatibility.json': other / 'compatibility.json',
                'fallback1-cpu-compat-analysis.log': other / 'compatibility-analysis.log',
                'fallback1-negative-analysis.log': other / 'negative-analysis.log',
                'fallback1-offline.log': SCRATCH / 'v2-offline-fallback1/offline.log',
            }.items():
                copy(path, folder / name)
            candidate['offline'] = {'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/diagnostic-execution-manifest.json --case {case_id} --candidate fallback1 --output .runtime-work/c143687-nov25a/v2-offline-fallback1 --python $PWD/.venv-cpu/bin/python',
                                    'exit_code': 0, 'construction_sha256': candidate['construction_sha256'],
                                    'log': f'cases/{suffix}/fallback1-offline.log',
                                    'log_sha256': sha(folder / 'fallback1-offline.log')}
            candidate['compatibility'] = {'receipt': f'cases/{suffix}/fallback1-compatibility.json',
                                          'sha256': sha(folder / 'fallback1-compatibility.json'),
                                          'log': f'cases/{suffix}/fallback1-cpu-compat-analysis.log',
                                          'negative_log': f'cases/{suffix}/fallback1-negative-analysis.log'}
        entries.append(entry)
    result = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
              'runtime_manifest_sha256': diagnostic['runtime_manifest_sha256'],
              'status': 'source_gated_cpu_preparation', 'original_delivery_claimed': False,
              'cases': entries}
    (HERE / 'execution-manifest.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('Bound three exact bicycle intents to diagnostic CPU receipts')


if __name__ == '__main__':
    main()
