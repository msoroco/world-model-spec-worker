"""Bind current baseline CPU proof files without claiming delivery readiness."""
import json
from hashlib import sha256
from pathlib import Path
from shutil import copyfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__baseline_right'


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def bind():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = manifest['cases'][0]
    if entry['case_id'] != CASE:
        raise ValueError('First baseline identity changed')
    compat = ROOT / '.runtime-work/c230259-baseline-right-compat-3'
    saved = ROOT / '.runtime-work/c230259-baseline-right-saved-2/v0001'
    offline = ROOT / '.runtime-work/c230259-baseline-right-offline-2/offline.log'
    if not json.loads((saved / 'processing.json').read_text())['missing_evidence'] is False:
        raise ValueError('Saved processing did not complete')
    copies = {
        'baseline-right-compatibility.json': compat / 'compatibility.json',
        'baseline-right-compat-analysis.log': compat / 'compatibility-analysis.log',
        'baseline-right-negative.log': compat / 'negative-analysis.log',
        'baseline-right-offline-tests.log': offline,
        'baseline-right-saved-processing.json': saved / 'processing.json',
        'baseline-right-saved-analysis.log': saved / 'analysis.log',
    }
    for name, source in copies.items():
        copyfile(source, HERE / name)
    proof = json.loads((HERE / 'baseline-right-compatibility.json').read_text())
    if proof['construction_sha256'] != entry['construction_sha256']:
        raise ValueError('Construction proof stale')
    entry['acquisition'] = {'right_half_observation': {
        'entrypoint': 'runner.py', 'method': '20 Hz Native full-body road reference recorder',
        'evidence': 'ego_road_frames.jsonl, road_exception_context.json, trace.jsonl, video_frames.jsonl'}}
    entry['offline'] = {
        'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + HERE.name +
                   '/execution-manifest.json --case ' + CASE +
                   ' --output .runtime-work/c230259-baseline-right-offline-2',
        'exit_code': 0, 'log': 'baseline-right-offline-tests.log',
        'log_sha256': sha(HERE / 'baseline-right-offline-tests.log'),
        'construction_sha256': entry['construction_sha256']}
    entry['compatibility'] = {
        'receipt': 'baseline-right-compatibility.json',
        'sha256': sha(HERE / 'baseline-right-compatibility.json'),
        'log': 'baseline-right-compat-analysis.log',
        'negative_log': 'baseline-right-negative.log'}
    entry['negative'] = {'log': 'baseline-right-negative.log'}
    entry['post_capture'] = {
        'recorded_only': True,
        'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + HERE.name +
                   '/execution-manifest.json --case ' + CASE +
                   ' --attempt "$ATTEMPT" --output "$PROCESSING_OUTPUT" --library runtime/library --validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck',
        'feedback_command': 'cat "$PROCESSING_OUTPUT/v0001/feedback.json"',
        'test_log': 'first-baseline-saved-current.log',
        'test_log_sha256': sha(HERE / 'first-baseline-saved-current.log'),
        'test_exit_code': 0}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    return {name: sha(HERE / name) for name in copies}


if __name__ == '__main__':
    print(json.dumps(bind(), indent=2))
