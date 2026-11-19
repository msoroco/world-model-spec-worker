"""Reject three changes to a current selected synthetic delivery source."""
import argparse
import json
from pathlib import Path
import tempfile

from audit_delivery import audit

EXPECTED = {
    'missing': 'Missing delivery source: officer_signal_rows.jsonl',
    'tampered': 'Delivery result differs from independent raw-source measurement',
    'native': 'Missing delivery source: capture-seal.json',
}


def prove(attempt, case_id, kind):
    attempt = Path(attempt).resolve()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for item in attempt.iterdir():
            (root / item.name).symlink_to(item, target_is_directory=item.is_dir())
        if kind == 'missing':
            (root / 'officer_signal_rows.jsonl').unlink()
        elif kind == 'tampered':
            result_path = root / 'result.json'
            result = json.loads(result_path.read_text())
            result_path.unlink()
            result['target_checks'][0]['measured'] = not result['target_checks'][0]['measured']
            result_path.write_text(json.dumps(result) + '\n')
        try:
            audit(root, case_id, diagnostic=kind != 'native')
        except ValueError as error:
            if EXPECTED[kind] not in str(error):
                raise
            return {'kind': kind, 'rejected': True, 'error': str(error),
                    'case_id': case_id, 'source_attempt': str(attempt),
                    'original_native_accepted': False}
        raise ValueError('Changed source was accepted: ' + kind)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=tuple(EXPECTED), required=True)
    args = parser.parse_args()
    print(json.dumps(prove(args.attempt, args.case, args.kind), sort_keys=True))
