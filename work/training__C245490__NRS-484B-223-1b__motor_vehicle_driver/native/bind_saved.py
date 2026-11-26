"""Bind four recorded-only saved-processing results and one missing-source feedback."""
import hashlib
import json
from pathlib import Path

from build_selected import CASES

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text('\n'.join(line.rstrip() for line in source.read_text().splitlines()).rstrip() + '\n')


def main():
    manifest_path = PACKAGE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    scratch = ROOT / '.runtime-work' / 'c245490-owner'
    for suffix, entry in zip(CASES, manifest['cases']):
        version = scratch / ('saved-' + suffix + '-v2') / 'v0001'
        receipt = json.loads((version / 'processing.json').read_text())
        if (receipt['case_id'] != entry['case_id'] or
                receipt['native_revision']['construction_sha256'] != entry['construction_sha256'] or
                receipt['missing_evidence'] or not receipt['originals_preserved'] or
                not receipt['recorded_only']):
            raise ValueError('Saved-only case proof missing or mismatched: ' + suffix)
        folder = PACKAGE / 'saved' / suffix
        report = folder / 'processing.json'
        command_log = folder / 'process-saved.log'
        clean_copy(version / 'processing.json', report)
        clean_copy(scratch / ('saved-' + suffix + '-v2-stdout.log'), command_log)
        entry['saved_processing'] = {
            'receipt': str(report.relative_to(PACKAGE)), 'sha256': sha(report),
            'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' +
                       PACKAGE.name + '/execution-manifest.json --case ' + entry['case_id'] +
                       ' --attempt .runtime-work/c245490-owner/compat-' + suffix + '-v5' +
                       ' --output .runtime-work/c245490-owner/saved-' + suffix + '-v2' +
                       ' --library runtime/library --validator .runtime-work/c245490-owner/decoder/.lake/build/bin/adapterCheck',
            'test_log': str(command_log.relative_to(PACKAGE)),
            'test_log_sha256': sha(command_log), 'test_exit_code': 0,
            'scope': 'labelled synthetic saved-only proof; original Native physical and pixel acceptance pending',
        }
    negative_source = scratch / 'saved-negative-safe-stdout.log'
    if negative_source.is_file():
        if 'Missing required source: native-driver-checks.jsonl' not in negative_source.read_text():
            raise ValueError('Missing-source saved-only negative did not reject')
        output = PACKAGE / 'saved' / 'signal_before_safe' / 'missing-source-negative.log'
        clean_copy(negative_source, output)
        manifest['cases'][0]['saved_processing']['missing_source_negative'] = {
            'log': str(output.relative_to(PACKAGE)), 'log_sha256': sha(output),
            'exit_code': 1,
            'expected_error': 'Missing required source: native-driver-checks.jsonl'}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'saved_bound': len(manifest['cases']),
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
