"""Bind exact narrow software proofs while retaining partial status."""
import json
from hashlib import sha256
from pathlib import Path
from shutil import copyfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__narrow_left'


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def bind():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    compat = ROOT / '.runtime-work/c230259-narrow-left-compat-1'
    copies = {
        'narrow-left-compatibility.json': compat / 'compatibility.json',
        'narrow-left-compat-analysis.log': compat / 'compatibility-analysis.log',
        'narrow-left-negative.log': compat / 'negative-analysis.log',
        'narrow-left-offline-tests.log': ROOT / '.runtime-work/c230259-narrow-left-offline-1/offline.log',
        'narrow-left-saved-processing.json': ROOT / '.runtime-work/c230259-narrow-left-saved-1/v0001/processing.json',
        'narrow-left-saved-analysis.log': ROOT / '.runtime-work/c230259-narrow-left-saved-1/v0001/analysis.log',
    }
    for name, source in copies.items():
        copyfile(source, HERE / name)
    receipt = json.loads((HERE / 'narrow-left-compatibility.json').read_text())
    if receipt['construction_sha256'] != entry['construction_sha256']:
        raise ValueError('Narrow compatibility proof stale')
    saved = json.loads((HERE / 'narrow-left-saved-processing.json').read_text())
    if saved['missing_evidence'] or not saved['originals_preserved']:
        raise ValueError('Narrow saved proof incomplete')
    entry['acquisition'] = {'right_half_observation': {
        'entrypoint': 'narrow_runner.py',
        'method': '80-frame Native measured narrow-road and body-width readback',
        'evidence': 'ego_road_frames.jsonl, road_exception_context.json, trace.jsonl, video_frames.jsonl',
    }}
    entry['offline'] = {
        'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {CASE} --output .runtime-work/c230259-narrow-left-offline-1',
        'exit_code': 0, 'log': 'narrow-left-offline-tests.log',
        'log_sha256': sha(HERE / 'narrow-left-offline-tests.log'),
        'construction_sha256': entry['construction_sha256'],
    }
    entry['compatibility'] = {
        'receipt': 'narrow-left-compatibility.json',
        'sha256': sha(HERE / 'narrow-left-compatibility.json'),
        'log': 'narrow-left-compat-analysis.log',
        'negative_log': 'narrow-left-negative.log',
    }
    entry['negative'] = {'log': 'narrow-left-negative.log'}
    entry['post_capture'] = {
        'recorded_only': True,
        'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {CASE} --attempt "$ATTEMPT" --output "$PROCESSING_OUTPUT" --library runtime/library --validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck',
        'feedback_command': 'cat "$PROCESSING_OUTPUT/v0001/feedback.json"',
        'test_log': 'narrow-left-saved.log',
        'test_log_sha256': sha(HERE / 'narrow-left-saved.log'),
        'test_exit_code': 0,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    return {'manifest_sha256': sha(manifest_path),
            'narrow_construction_sha256': entry['construction_sha256']}


if __name__ == '__main__':
    print(json.dumps(bind()))
