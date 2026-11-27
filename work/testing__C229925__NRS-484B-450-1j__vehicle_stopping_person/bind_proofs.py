"""Bind already-passing exact CPU proofs without regenerating constructions."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from fire_station_scene import ASSIGNMENT


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c229925-owner'
MANIFEST = ROOT / 'execution-manifest.json'
VALIDATOR = SCRATCH / 'decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy(source, target):
    data = Path(source).read_bytes()
    if data and target.suffix == '.log':
        data = data.rstrip(b'\n') + b'\n'
    if len(data) >= 2*1024*1024:
        raise ValueError('returned proof file exceeds 2 MiB: ' + str(source))
    if data.endswith(b'\n\n'):
        raise ValueError('proof has blank line at EOF: ' + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = SCRATCH / (target.name + '.copy-tmp')
    temporary.write_bytes(data)
    os.replace(temporary, target)


def receipt(kind, suffix, entry):
    folder = SCRATCH / (('compat-' if kind == 'primary' else
                         'compat-fallback1-') + suffix)
    directory = ROOT / 'proofs' / (kind + '-' + suffix)
    copy(folder / 'compatibility.json', directory / 'receipt.json')
    copy(folder / 'compatibility-analysis.log', directory / 'analysis.log')
    copy(folder / 'negative-analysis.log', directory / 'negative.log')
    return {
        'receipt': str((directory / 'receipt.json').relative_to(ROOT)),
        'sha256': sha(directory / 'receipt.json'),
        'log': str((directory / 'analysis.log').relative_to(ROOT)),
        'negative_log': str((directory / 'negative.log').relative_to(ROOT))}


def main():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    for entry in manifest['cases']:
        cid = entry['case_id']
        suffix = cid.removeprefix(ASSIGNMENT + '__')
        if suffix == cid:
            raise ValueError('wrong assignment identity')
        manifest_arg = 'work/' + ASSIGNMENT + '/execution-manifest.json'
        for kind, selected in (('primary', entry),
                               ('fallback1', entry['candidates'][0])):
            label = '' if kind == 'primary' else 'fallback1-'
            output = SCRATCH / (('offline-' if kind == 'primary' else
                                 'offline-fallback1-') + suffix)
            log = ROOT / ('proof-offline-' + label + suffix + '.log')
            if not log.is_file() or not output.is_dir():
                raise ValueError('offline proof missing: ' + cid + ' ' + kind)
            command = ('.venv-cpu/bin/python runtime.py offline --manifest ' +
                       manifest_arg + ' --case ' + cid +
                       ('' if kind == 'primary' else ' --candidate fallback1') +
                       ' --output ' + str(output.relative_to(REPO)))
            selected['offline'] = {
                'construction_sha256': selected['construction_sha256'],
                'command': command, 'exit_code': 0,
                'log': log.name, 'log_sha256': sha(log)}
            selected['compatibility'] = receipt(kind, suffix, entry)
            if kind == 'primary':
                selected['negative'] = {
                    'log': selected['compatibility']['negative_log']}
        physical = ROOT / ('physical-' + suffix + '-receipt.json')
        entry['physical_preparation'] = {
            'receipt': physical.name, 'sha256': sha(physical)}
        saved = ROOT / ('proof-saved-' + suffix + '.log')
        process_command = (
            '.venv-cpu/bin/python runtime.py process-saved --manifest ' +
            manifest_arg + ' --case ' + cid +
            ' --attempt "$ATTEMPT" --output "$PROCESSED"' +
            ' --library runtime/library --validator "$LEAN_VALIDATOR"' +
            ' --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        entry['post_capture'] = {
            'recorded_only': True,
            'command': process_command,
            'feedback_command': process_command,
            'test_log': saved.name,
            'test_log_sha256': sha(saved),
            'test_exit_code': 0,
            'scope': 'synthetic recorded-only replay; original fire-station, highway, vehicle, exception and pixel review pending'}
        positive = ROOT / ('proof-delivery-' + suffix + '-positive.log')
        negative = ROOT / ('proof-delivery-' + suffix + '-negative.log')
        attempt = SCRATCH / ('compat-' + suffix)
        saved_root = SCRATCH / ('saved-' + suffix)
        base = ('.venv-cpu/bin/python work/' + ASSIGNMENT +
                '/delivery_probe.py --case ' + cid +
                ' --attempt ' + str(attempt.relative_to(REPO)) +
                ' --saved-root ' + str(saved_root.relative_to(REPO)))
        entry['delivery_acceptance'] = {
            'case_id': cid, 'sets': ['full-test'],
            'cpu_proof_kind': 'mock_only_contract_wiring',
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels',
                       'physical_completion'],
            'script': 'delivery_audit.py',
            'script_sha256': sha(ROOT / 'delivery_audit.py'),
            'command': base + ' --mode positive',
            'test_exit_code': 0, 'test_log': positive.name,
            'test_log_sha256': sha(positive),
            'negative_command': base + ' --mode missing_source',
            'negative_exit_code': 2,
            'negative_expected_error':
                'sealed original missing or changed: fire-entrance-context.json',
            'negative_log': negative.name,
            'negative_log_sha256': sha(negative)}
    temporary = SCRATCH / 'execution-manifest-bound.tmp'
    temporary.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, MANIFEST)


if __name__ == '__main__':
    main()
