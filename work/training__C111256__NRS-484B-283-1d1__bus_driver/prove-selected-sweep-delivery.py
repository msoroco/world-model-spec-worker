"""Audit four sweep primaries against the canonical selected case inventory."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = read(manifest_path)
    selected = [entry for entry in manifest['cases']
                if '__right_of_way_physical_context-' in entry['case_id']]
    if len(manifest['cases']) != 6 or len(selected) != 4:
        raise ValueError('Canonical sweep selection differs')
    source_root = REPO / '.runtime-work/c111256-update033-sweep-delivery'
    rows = []
    for entry in selected:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        attempt = source_root / suffix / 'attempt'
        processing = source_root / suffix / 'processed/v0001/processing.json'
        destination = HERE / 'update037-selected-sweep-delivery' / suffix
        if destination.exists():
            raise ValueError('Retain prior selected sweep delivery proof; use a fresh tag')
        destination.mkdir(parents=True)
        common = [str(PYTHON), str(HERE / 'sweep_delivery_audit.py'),
                  '--manifest', str(manifest_path), '--case', case,
                  '--candidate', 'primary', '--attempt', str(attempt),
                  '--processing', str(processing)]
        positive = [*common, '--output', str(destination / 'diagnostic.json'), '--diagnostic']
        good = subprocess.run(positive, cwd=REPO, capture_output=True, text=True, timeout=300)
        positive_log = destination / 'diagnostic.log'
        positive_log.write_text(good.stdout + good.stderr)
        if good.returncode or not (destination / 'diagnostic.json').is_file():
            raise ValueError('Canonical sweep diagnostic audit failed: ' + positive_log.read_text()[-1200:])
        checked = read(destination / 'diagnostic.json')
        if checked['passed'] is not False or checked['source_shaped_unit_test'] is not True:
            raise ValueError('Diagnostic delivery claimed original acceptance')
        negative = [*common, '--output', str(destination / 'original-rejection.json')]
        bad = subprocess.run(negative, cwd=REPO, capture_output=True, text=True, timeout=300)
        negative_log = destination / 'original-rejection.log'
        negative_log.write_text(bad.stdout + bad.stderr)
        if (bad.returncode == 0 or (destination / 'original-rejection.json').exists()
                or 'Original Native Walk source required' not in negative_log.read_text()):
            raise ValueError('Synthetic source passed canonical original review')
        rows.append({'case_id': case,
                     'construction_sha256': entry['construction_sha256'],
                     'diagnostic_command': ' '.join(positive),
                     'diagnostic_log': positive_log.relative_to(HERE).as_posix(),
                     'diagnostic_log_sha256': sha(positive_log),
                     'diagnostic_result_sha256': sha(destination / 'diagnostic.json'),
                     'negative_command': ' '.join(negative),
                     'negative_log': negative_log.relative_to(HERE).as_posix(),
                     'negative_log_sha256': sha(negative_log),
                     'negative_exit_code': bad.returncode,
                     'negative_expected_error': 'Original Native Walk source required'})
        print(suffix, 'canonical diagnostic and original rejection passed', flush=True)
    matrix = HERE / 'update037-selected-sweep-delivery-matrix.json'
    matrix.write_text(json.dumps({'format': 'c111256-selected-sweep-delivery-matrix-v1',
                                  'manifest_sha256': sha(manifest_path),
                                  'auditor_sha256': sha(HERE / 'sweep_delivery_audit.py'),
                                  'rows': rows, 'diagnostic_passed': 4,
                                  'original_rejections_passed': 4,
                                  'original_recordings_accepted': 0}, indent=2) + '\n')
    print(json.dumps({'cases': 4, 'matrix_sha256': sha(matrix),
                      'original_recordings_accepted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
