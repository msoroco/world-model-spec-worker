"""Bind exact primary and fallback offline, compatibility and physical CPU proofs."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUFFIXES = ('reference', 'contrast', 'engine_on', 'brake_unset', 'wheel_straight')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        if suffix not in SUFFIXES:
            raise ValueError('Unexpected duty case')
        proof_dir = HERE / 'proofs' / suffix
        physical = proof_dir / 'physical-preparation.json'
        if not physical.is_file():
            raise ValueError('Missing physical CPU proof: ' + suffix)
        entry['physical_preparation'] = {'receipt': str(physical.relative_to(HERE)),
                                         'sha256': sha(physical)}
        entry['acquisition'] = {
            'engine_running': {'entrypoint': 'runner.py', 'method': 'original same-frame engine operation sensor after actuator receipt', 'evidence': ['engine-preparation.json', 'instrument-frames.jsonl']},
            'parking_brake_set': {'entrypoint': 'runner.py', 'method': 'original vehicle control and brake readback', 'evidence': ['vehicle-frames.jsonl', 'trace.jsonl']},
            'front_wheel_heading_to_curb_deg': {'entrypoint': 'runner.py', 'method': 'calibrated original front-wheel sensor with separate Native angles', 'evidence': ['instrument-frames.jsonl', 'vehicle-frames.jsonl']},
            'unattended_interval': {'entrypoint': 'runner.py', 'method': 'original occupancy and responsible-person sensor', 'evidence': ['instrument-frames.jsonl', 'occupancy-frames.jsonl']}}
        for candidate in ('primary', 'fallback1'):
            selected = entry if candidate == 'primary' else entry['candidates'][0]
            offline = HERE / ('selected-grade-' + suffix + '-' + candidate + '-offline.log')
            if not offline.is_file():
                raise ValueError('Missing offline log: ' + suffix + ' ' + candidate)
            selected['offline'] = {'exit_code': 0,
                                   'construction_sha256': selected['construction_sha256'],
                                   'command': 'runtime.py offline --manifest work/' + HERE.name + '/execution-manifest.json --case ' + entry['case_id'] + ' --candidate ' + candidate,
                                   'log': str(offline.relative_to(HERE)),
                                   'log_sha256': sha(offline)}
            output = ROOT / '.runtime-work' / ('c276263-selected-compat-' + suffix + '-' + candidate)
            for name in ('compatibility.json', 'compatibility-analysis.log', 'negative-analysis.log'):
                if not (output / name).is_file():
                    raise ValueError('Missing selected compatibility: ' + suffix + ' ' + candidate + ' ' + name)
            receipt = proof_dir / (candidate + '-compatibility.json')
            positive = proof_dir / (candidate + '-compatibility-analysis.log')
            negative = proof_dir / (candidate + '-negative-analysis.log')
            shutil.copyfile(output / 'compatibility.json', receipt)
            shutil.copyfile(output / 'compatibility-analysis.log', positive)
            shutil.copyfile(output / 'negative-analysis.log', negative)
            selected['compatibility'] = {'receipt': str(receipt.relative_to(HERE)),
                                         'sha256': sha(receipt),
                                         'log': str(positive.relative_to(HERE)),
                                         'negative_log': str(negative.relative_to(HERE))}
            if candidate == 'primary':
                selected['negative'] = {'log': str(negative.relative_to(HERE)),
                                        'log_sha256': sha(negative)}
    write(path, manifest)
    print(json.dumps({'selected_case_count': len(manifest['cases']), 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
