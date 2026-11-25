"""Bind recorded-only selected processing receipts for both candidates."""
import hashlib
import json
import shutil
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = FOLDER / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__', 1)[-1]
        for candidate, choice in [('primary', entry), ('fallback1', entry['candidates'][0])]:
            source = REPO / '.runtime-work' / f'c111325-saved-output-{condition}-{candidate}' / 'v0001' / 'processing.json'
            receipt = json.loads(source.read_text())
            if not receipt.get('passed') or not receipt.get('recorded_only') or receipt.get('case_id') != entry['case_id'] or receipt.get('candidate_id') != candidate:
                raise ValueError(f'Saved processing failed: {condition} {candidate}')
            if receipt['native_revision']['construction_sha256'] != choice['construction_sha256']:
                raise ValueError(f'Stale construction: {condition} {candidate}')
            folder = FOLDER / 'proofs' / condition / candidate
            target = folder / 'processing.json'
            shutil.copyfile(source, target)
            choice['saved_processing'] = {'receipt': str(target.relative_to(FOLDER)), 'sha256': sha(target)}
            if candidate == 'primary':
                log = FOLDER / f'saved-{condition}-primary.log'
                shutil.copyfile(source, log)
                choice['post_capture'] = {
                    'recorded_only': True,
                    'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{FOLDER.name}/execution-manifest.json --case {entry["case_id"]} --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library',
                    'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
                    'test_exit_code': 0,
                    'test_log': log.name,
                    'test_log_sha256': sha(log),
                }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'saved_bound': 4, 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
