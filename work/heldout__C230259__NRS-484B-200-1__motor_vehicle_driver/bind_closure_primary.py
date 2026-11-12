"""Bind exact closure software proofs; retain the assignment's partial status."""
import json
from hashlib import sha256
from pathlib import Path
from shutil import copyfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__closure_left'


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def bind():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    compat = ROOT / '.runtime-work/c230259-closure-left-compat-4'
    copies = {
        'closure-left-compatibility.json': compat / 'compatibility.json',
        'closure-left-compat-analysis.log': compat / 'compatibility-analysis.log',
        'closure-left-negative.log': compat / 'negative-analysis.log',
        'closure-left-offline-tests.log': ROOT / '.runtime-work/c230259-closure-left-offline-2/offline.log',
        'closure-left-saved-processing.json': ROOT / '.runtime-work/c230259-closure-left-saved-2/v0001/processing.json',
        'closure-left-saved-analysis.log': ROOT / '.runtime-work/c230259-closure-left-saved-2/v0001/analysis.log',
    }
    for name, source in copies.items():
        copyfile(source, HERE / name)
    receipt = json.loads((HERE / 'closure-left-compatibility.json').read_text())
    if receipt['construction_sha256'] != entry['construction_sha256']:
        raise ValueError('Closure compatibility proof stale')
    saved = json.loads((HERE / 'closure-left-saved-processing.json').read_text())
    if saved['missing_evidence'] or not saved['originals_preserved']:
        raise ValueError('Closure saved proof incomplete')
    entry['acquisition'] = {'right_half_observation': {
        'entrypoint': 'closure_runner.py',
        'method': '80-frame Native full-body/directed-road and three-device closure readback',
        'evidence': 'ego_road_frames.jsonl, closure_devices.jsonl, road_exception_context.json, trace.jsonl, video_frames.jsonl',
    }}
    entry['offline'] = {
        'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {CASE} --output .runtime-work/c230259-closure-left-offline-2',
        'exit_code': 0, 'log': 'closure-left-offline-tests.log',
        'log_sha256': sha(HERE / 'closure-left-offline-tests.log'),
        'construction_sha256': entry['construction_sha256'],
    }
    entry['compatibility'] = {
        'receipt': 'closure-left-compatibility.json',
        'sha256': sha(HERE / 'closure-left-compatibility.json'),
        'log': 'closure-left-compat-analysis.log',
        'negative_log': 'closure-left-negative.log',
    }
    entry['negative'] = {'log': 'closure-left-negative.log'}
    entry['post_capture'] = {
        'recorded_only': True,
        'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {CASE} --attempt "$ATTEMPT" --output "$PROCESSING_OUTPUT" --library runtime/library --validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck',
        'feedback_command': 'cat "$PROCESSING_OUTPUT/v0001/feedback.json"',
        'test_log': 'closure-left-saved.log',
        'test_log_sha256': sha(HERE / 'closure-left-saved.log'),
        'test_exit_code': 0,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    return {'manifest_sha256': sha(manifest_path),
            'closure_construction_sha256': entry['construction_sha256']}


if __name__ == '__main__':
    print(json.dumps(bind()))
