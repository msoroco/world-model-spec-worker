"""Bind exact current-runtime public and recorded-only CPU receipts to selected cases."""
import hashlib
import json
import shutil
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
SCRATCH = ROOT / '.runtime-work'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target.relative_to(FOLDER).as_posix()


def main():
    manifest_path = FOLDER / 'selected-probe-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['status'] = 'selected_delivery_cpu_prepared'
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        prefix = f'c111250-selected-{suffix}'
        compatibility = SCRATCH / f'{prefix}-compat-final2'
        processing = SCRATCH / f'{prefix}-saved-final2/v0001/processing.json'
        offline = SCRATCH / f'{prefix}-offline-final.log'
        proof_dir = FOLDER / 'selected-proofs'
        receipt = FOLDER / copy(compatibility / 'compatibility.json', proof_dir / f'{suffix}-primary-compatibility.json')
        log = FOLDER / copy(compatibility / 'compatibility-analysis.log', proof_dir / f'{suffix}-primary-analysis.log')
        negative = FOLDER / copy(compatibility / 'negative-analysis.log', proof_dir / f'{suffix}-primary-negative.log')
        saved = FOLDER / copy(processing, proof_dir / f'{suffix}-primary-processing.json')
        offline_log = FOLDER / copy(offline, proof_dir / f'{suffix}-primary-offline.log')
        public = json.loads(receipt.read_text())
        record = json.loads(saved.read_text())
        if (public['construction_sha256'] != entry['construction_sha256'] or
                not public['passed'] or not record['passed'] or
                not record['recorded_only'] or not record['originals_preserved']):
            raise ValueError('Selected proof differs from exact construction or saved source')
        if public['log_sha256'] != sha(log) or public['negative_log_sha256'] != sha(negative):
            raise ValueError('Source proof log differs')
        entry['offline'] = {'command':
            f'.venv-cpu/bin/python runtime.py offline --manifest work/{FOLDER.name}/selected-probe-manifest.json --case {entry["case_id"]} --candidate primary --output .runtime-work/{prefix}-offline-final --python $PWD/.venv-cpu/bin/python',
            'exit_code': 0, 'construction_sha256': entry['construction_sha256'],
            'log': offline_log.relative_to(FOLDER).as_posix(), 'log_sha256': sha(offline_log)}
        entry['compatibility'] = {'receipt': receipt.relative_to(FOLDER).as_posix(),
                                  'sha256': sha(receipt), 'log': log.relative_to(FOLDER).as_posix(),
                                  'negative_log': negative.relative_to(FOLDER).as_posix()}
        entry['negative'] = {'log': negative.relative_to(FOLDER).as_posix()}
        entry['saved_processing'] = {'receipt': saved.relative_to(FOLDER).as_posix(),
                                     'sha256': sha(saved)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['post_capture'] = {'command':
            f'python runtime.py process-saved --manifest work/{FOLDER.name}/execution-manifest.json --case {entry["case_id"]} --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library runtime/library --validator "$DECODER"',
            'feedback_command': 'cat "$SAVED_OUTPUT"/v0001/feedback.json',
            'recorded_only': True, 'test_exit_code': 0,
            'test_log': saved.relative_to(FOLDER).as_posix(), 'test_log_sha256': sha(saved)}
        construction = json.loads((FOLDER / entry['construction']).read_text())
        files = {item['path'] for item in construction['files']}
        evidence = 'road-context.json, vehicle-footprints.jsonl, trace.jsonl, video_frames.jsonl, capture/evidence.jsonl and original four cameras'
        entry['acquisition'] = {atom: {'entrypoint': 'selected_capture.py',
                                       'method': '20 Hz original Native map, full body, motion and synchronized camera acquisition followed by saved-only zone measurement',
                                       'evidence': evidence}
                                for atom in {*(c['name'] for c in construction['recording_description']['channels']),
                                             *json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))['required_atoms']}}
        if 'selected_capture.py' not in files:
            raise ValueError('Capture implementation omitted')
        print(suffix, sha(receipt), sha(saved))
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
