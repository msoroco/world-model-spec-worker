"""Freeze the twelve active-runtime source-bound CPU chains for return."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / '.runtime-work'
TARGET = HERE / 'current-public'
SUFFIXES = ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if len(manifest['cases']) != 4:
        raise ValueError('Four selected exact cases required')
    TARGET.mkdir(exist_ok=True)
    records = []
    for suffix in SUFFIXES:
        case = HERE.name + '__' + suffix
        for candidate in CANDIDATES:
            key = suffix + '-' + candidate
            attempt = SOURCE / ('c10316-d4-compat-witness1-primary-v8' if key == 'witness_1-primary'
                                else 'c10316-d4-compat-' + key)
            saved = SOURCE / ('c10316-d4-saved-' + ('witness1' if key == 'witness_1-primary' else suffix) + '-' + candidate)
            paths = {
                'compatibility': attempt / 'compatibility.json',
                'analysis_log': attempt / 'compatibility-analysis.log',
                'negative_log': attempt / 'negative-analysis.log',
                'processing': saved / 'v0001/processing.json',
            }
            compatibility = json.loads(paths['compatibility'].read_text())
            processing = json.loads(paths['processing'].read_text())
            if (compatibility['case_id'], compatibility['candidate_id'], compatibility['passed']) != (case, candidate, True):
                raise ValueError('Compatibility identity or pass differs: ' + key)
            if (processing['case_id'], processing['candidate_id'], processing['passed'], processing['recorded_only']) != (case, candidate, True, True):
                raise ValueError('Saved replay identity or pass differs: ' + key)
            copied = {}
            for label, path in paths.items():
                target = TARGET / (key + '-' + label + path.suffix)
                shutil.copyfile(path, target)
                copied[label] = {'path': target.relative_to(HERE).as_posix(), 'sha256': sha(target)}
            records.append({'case_id': case, 'candidate': candidate, 'artifacts': copied,
                            'attempt': attempt.relative_to(ROOT).as_posix(),
                            'saved_output': saved.relative_to(ROOT).as_posix()})
    summary = {'format': 'c10316-d4-current-chain-proof', 'passed': True,
               'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
               'selected_manifest_sha256': sha(manifest_path), 'cases': 4,
               'chains': records, 'physical_observed': False}
    path = TARGET / 'proof.json'
    path.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'chains': len(records), 'proof_sha256': sha(path)}))


if __name__ == '__main__':
    main()
