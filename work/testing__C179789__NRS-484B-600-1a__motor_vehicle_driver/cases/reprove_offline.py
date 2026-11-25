"""Materialize and check all eight source-bound diagnostic constructions."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
OUT = REPO / '.runtime-work/c179789-sweep'
SUFFIXES = ('dry_4mps', 'dry_open_traffic', 'dry_6mps',
            'wet_same_traffic', 'narrow_same_traffic', 'dense_traffic',
            'low_visibility', 'ice_or_snow')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    previous = json.loads((ROOT / 'cases/condition-offline-index.json').read_text())
    entries = []
    for suffix in SUFFIXES:
        case = 'testing__C179789__NRS-484B-600-1a__motor_vehicle_driver__' + suffix
        rel = 'construction.json' if suffix == 'dry_open_traffic' else 'cases/' + suffix + '-construction.json'
        source = ROOT / rel
        folder = OUT / suffix
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, folder / 'construction.json')
        manifest = folder / 'manifest.json'
        manifest.write_text(json.dumps({'cases': [{'case_id': case,
                                                  'construction': 'construction.json',
                                                  'construction_sha256': sha(source)}]}, indent=2) + '\n')
        attempt = folder / ('offline-attempt-' + sha(source)[:12])
        log = ROOT / 'cases' / (suffix + '-current-offline.log')
        command = ['.venv-cpu/bin/python', 'runtime.py', 'offline',
                   '--manifest', str(manifest.relative_to(REPO)),
                   '--case', case, '--output', str(attempt.relative_to(REPO))]
        with log.open('w') as stream:
            result = subprocess.run(command, cwd=REPO, stdout=stream,
                                    stderr=subprocess.STDOUT, check=False)
        entries.append({'case_id': case, 'candidate_id': 'primary',
                        'construction': rel, 'construction_sha256': sha(source),
                        'command': ' '.join(command), 'exit_code': result.returncode,
                        'log': 'cases/' + log.name, 'log_sha256': sha(log),
                        'simulation_started': False, 'source_packet_kind': 'synthetic diagnostic',
                        'delivery_ready': False,
                        'embedded_finalizer_and_measurement_contract': True,
                        'embedded_independent_audit': True,
                        'embedded_tests_passed': 24 if result.returncode == 0 else 0})
        print(suffix, result.returncode, flush=True)
        if result.returncode:
            break
    index = {'format': previous['format'],
             'runtime_source_manifest_sha256': previous['runtime_source_manifest_sha256'],
             'cases': entries}
    (ROOT / 'cases/condition-offline-index.json').write_text(json.dumps(index, indent=2) + '\n')
    if len(entries) != len(SUFFIXES) or any(row['exit_code'] for row in entries):
        sys.exit(1)


if __name__ == '__main__':
    main()
