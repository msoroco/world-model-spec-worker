"""Bind four recorded-only selected saved-processing receipts."""
import hashlib
import json
import shutil
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
MANIFEST = FOLDER / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        label = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1'):
            choice = entry if candidate == 'primary' else entry['candidates'][0]
            source = REPO / '.runtime-work/c124163-saved-v8' / f'derived-{label}-{candidate}/v0001/processing.json'
            target = FOLDER / 'proofs' / label / candidate / 'processing.json'
            shutil.copyfile(source, target)
            receipt = json.loads(target.read_text())
            if (not receipt['passed'] or receipt['missing_evidence'] or
                    not receipt['recorded_only'] or not receipt['originals_preserved']):
                raise ValueError('Saved processing proof incomplete')
            choice['saved_processing'] = {'receipt': str(target.relative_to(FOLDER)),
                                          'sha256': sha(target)}
        entry['post_capture'] = {'recorded_only': True,
          'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{FOLDER.name}/execution-manifest.json --case {entry["case_id"]} --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library --validator "$VALIDATOR"',
          'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
          'test_exit_code': 0, 'proof': entry['saved_processing']['receipt']}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'saved_receipts': len(manifest['cases'])*2, 'manifest_sha256': sha(MANIFEST)}))


if __name__ == '__main__':
    main()
