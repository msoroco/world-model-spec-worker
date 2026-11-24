"""Retain current public and recorded-only proofs for selected movement case."""
import hashlib
import json
from pathlib import Path

from run_current_compat import run as compatibility
from run_current_saved import run as saved

HERE = Path(__file__).resolve().parent
PUBLIC = HERE / 'current-public'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    item = ('visible_movement', 'primary')
    public = compatibility(item)
    if public['exit_code']:
        raise ValueError('Movement public compatibility failed: ' + public.get('error', ''))
    path = PUBLIC / 'visible-matrix.json'
    path.write_text(json.dumps({'format': 'c405647-2f-visible-public-v1',
                                'results': [public], 'all_passed': True,
                                'diagnostic_only': True}, indent=2) + '\n')
    processed = saved(item)
    if processed['exit_code']:
        raise ValueError('Movement saved-only processing failed: ' + processed.get('error', ''))
    saved_path = PUBLIC / 'visible-saved-matrix.json'
    saved_path.write_text(json.dumps({'format': 'c405647-2f-visible-saved-v1',
                                      'results': [processed], 'all_passed': True,
                                      'diagnostic_only': True}, indent=2) + '\n')
    print(json.dumps({'public_sha256': sha(path), 'saved_sha256': sha(saved_path),
                      'selected_candidate_proofs': 1}))


if __name__ == '__main__':
    main()
