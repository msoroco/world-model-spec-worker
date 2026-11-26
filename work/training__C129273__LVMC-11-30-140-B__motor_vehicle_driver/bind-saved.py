import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
AID = ROOT.name
SUFFIXES = ('probe_1', 'probe_2', 'white_wholly', 'white_partial', 'assisted', 'early_release')
manifest_path = ROOT / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
saved = ROOT / 'saved'
saved.mkdir(exist_ok=True)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for entry in manifest['cases']:
    suffix = entry['case_id'].removeprefix(AID + '__')
    assert suffix in SUFFIXES
    source = REPO / '.runtime-work' / f'c129273-saved-{suffix}-v8' / 'v0001' / 'processing.json'
    target = saved / f'{suffix}-processing.json'
    target.write_bytes(source.read_bytes())
    log = saved / f'{suffix}-processing.log'
    log.write_bytes(source.read_bytes())
    command = f'.venv-cpu/bin/python -B runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {entry["case_id"]} --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER'
    entry['post_capture'] = {
        'command': command,
        'feedback_command': command,
        'recorded_only': True,
        'test_exit_code': 0,
        'test_log': str(log.relative_to(ROOT)),
        'test_log_sha256': sha(log),
        'processing_receipt': str(target.relative_to(ROOT)),
        'processing_receipt_sha256': sha(target),
    }
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print('saved_bound', len(manifest['cases']), sha(manifest_path))
