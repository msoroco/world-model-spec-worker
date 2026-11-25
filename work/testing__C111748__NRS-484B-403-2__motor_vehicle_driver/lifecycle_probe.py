"""CPU probe of original capture, exit, release and saved-processing order."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from worker_exchange.saved_processing import acknowledge_owner_release, record_native_exit, _closure


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root: Path) -> dict:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    (root / 'construction.json').write_text('{"case_id":"diagnostic"}\n')
    (root / 'device-native.json').write_text('{"diagnostic":true}\n')
    source = {'device-native.json': sha(root / 'device-native.json')}
    seal = {'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
            'sources': source, 'native_revision': {'construction_sha256': sha(root / 'construction.json'),
                                                    'runner_sha256': 'diagnostic-runner'}}
    (root / 'capture-seal.json').write_text(json.dumps(seal) + '\n')
    before = sha(root / 'device-native.json')
    exit_receipt = record_native_exit(root)
    if exit_receipt['event'] != 'native_exit':
        raise ValueError('Native exit event missing')
    owner_path = root / 'owner-release.json'
    try:
        acknowledge_owner_release(root, owner_path, False)
    except ValueError as error:
        if 'attest' not in str(error):
            raise
    else:
        raise ValueError('unattested owner release accepted')
    owner = acknowledge_owner_release(root, owner_path, True)
    if owner['event'] != 'owner_released':
        raise ValueError('owner release event missing')
    _closure(root, owner_path, 'native', False)
    original = (root / 'device-native.json').read_text()
    (root / 'device-native.json').write_text(original + 'tampered\n')
    try:
        _closure(root, owner_path, 'native', False)
    except ValueError as error:
        if 'Sealed original changed' not in str(error):
            raise
    else:
        raise ValueError('stale original accepted after release')
    (root / 'device-native.json').write_text(original)
    if sha(root / 'device-native.json') != before:
        raise ValueError('original source not restored')
    return {'events': [*seal['events'], 'native_exit', 'owner_released',
                       'saved_processing_started'], 'exit_code': 0,
            'negative_unattested_release_rejected': True,
            'negative_stale_original_rejected': True,
            'diagnostic_fixture': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.scratch), sort_keys=True))


if __name__ == '__main__':
    main()
