"""Bind selected production intent to diagnostic CPU proofs without promotion."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from one_way_direction import CASES


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / '.runtime-work/c147311-nov25e'
ASSIGNMENT = HERE.name


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    diagnostic = json.loads((HERE / 'diagnostic-execution-manifest.json').read_text())
    entries = []
    for source in diagnostic['cases']:
        case_id = source['case_id']
        suffix = case_id.removeprefix(ASSIGNMENT + '__')
        if suffix not in {c.name for c in CASES}:
            raise ValueError('nonselected case')
        folder = HERE / 'cases' / suffix
        attempt = REPO / '.runtime-work' / ('c147311-compat-' + suffix + '-v13')
        origin = {
            'compatibility.json': attempt / 'compatibility.json',
            'cpu-compat-analysis.log': attempt / 'compatibility-analysis.log',
            'negative-analysis.log': attempt / 'negative-analysis.log',
        }
        for name, path in origin.items():
            shutil.copyfile(path, folder / name)
        saved = HERE / ('cpu-pinned-saved-' + suffix + '.json')
        construction_sha = source['construction_sha256']
        physics = folder / 'physical-preparation.json'
        positive = folder / 'delivery-positive.log'
        negative = folder / 'delivery-negative.log'
        script = HERE / 'prove_delivery_contract.py'
        command = f'.venv-cpu/bin/python work/{ASSIGNMENT}/prove_delivery_contract.py --case {case_id}'
        entry = dict(source)
        entry.update(kind='delivery', status='source_gated_cpu_preparation',
                     offline={'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/diagnostic-execution-manifest.json --case {case_id} --output .runtime-work/c147311-offline-{suffix}-v13',
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
                         'case_id': case_id, 'sets': ['demo-test', 'full-test'],
                         'checks': ['native_source', 'all_participants', 'time_join',
                                    'full_video_decode', 'actual_pixels', 'physical_completion'],
                         'scope': 'synthetic protocol CPU proof; original delivery pending',
                         'diagnostic_fixture': True,
                         'command': command + ' --mode diagnostic-positive',
                         'test_exit_code': 0,
                         'test_log': f'cases/{suffix}/delivery-positive.log',
                         'test_log_sha256': sha(positive),
                         'negative_command': command + ' --mode delivery-negative',
                         'negative_exit_code': 1,
                         'negative_expected_error': 'successful released original Native attempt required',
                         'negative_log': f'cases/{suffix}/delivery-negative.log',
                         'negative_log_sha256': sha(negative),
                         'script': 'delivery_audit.py',
                         'script_sha256': sha(HERE / 'delivery_audit.py')},
                     post_capture={
                         'recorded_only': True,
                         'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case_id} --attempt $ATTEMPT --output $DERIVED --library runtime/library --validator $VALIDATOR --owner-release-receipt $OWNER_RELEASE_RECEIPT',
                         'feedback_command': f'.venv-cpu/bin/python work/{ASSIGNMENT}/delivery_audit.py --authority-root $SOURCE_ROOT --receipt $RECEIPT --output $AUDIT',
                         'test_log': saved.name, 'test_log_sha256': sha(saved),
                         'test_exit_code': 0},
                     native_handoff={'python_env_var': 'CARLA_PYTHON',
                                     'host_env_var': 'CARLA_HOST',
                                     'port_env_var': 'CARLA_PORT'},
                     pending_original_sources=['reviewed original one-way highway/site and sign authority',
                                               'accepted lane-one source trace/video',
                                               'released Native four-camera selected attempts'])
        construction = json.loads((HERE / source['construction']).read_text())
        required = {ch['name'] for ch in construction['recording_description']['channels']}
        entry['acquisition'] = {name: {'entrypoint': 'native_adapter.py',
                                       'method': 'capture',
                                       'evidence': 'source-gated original Native sign/route/camera readback'}
                                for name in sorted(required)}
        entries.append(entry)
    result = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
              'runtime_manifest_sha256': diagnostic['runtime_manifest_sha256'],
              'status': 'source_gated_cpu_preparation',
              'original_delivery_claimed': False, 'cases': entries}
    (HERE / 'execution-manifest.json').write_text(
        json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('Bound four exact one-way selected intents to diagnostic CPU proofs')


if __name__ == '__main__':
    main()
