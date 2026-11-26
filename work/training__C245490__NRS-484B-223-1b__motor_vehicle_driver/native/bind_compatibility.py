"""Bind four selected positive and missing-source public CPU receipts."""
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
    text = '\n'.join(line.rstrip() for line in source.read_text().splitlines()).rstrip()
    destination.write_text(text + '\n')


def main():
    path = PACKAGE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for suffix, entry in zip(CASES, manifest['cases']):
        source = ROOT / '.runtime-work' / 'c245490-owner' / ('compat-' + suffix + '-v4')
        receipt = json.loads((source / 'compatibility.json').read_text())
        if (not receipt['passed'] or receipt['case_id'] != entry['case_id'] or
                receipt['construction_sha256'] != entry['construction_sha256']):
            raise ValueError('Selected public proof absent or stale: ' + suffix)
        folder = PACKAGE / 'proofs' / suffix
        analysis = folder / 'analysis.log'
        negative = folder / 'negative-analysis.log'
        clean_copy(source / 'compatibility-analysis.log', analysis)
        clean_copy(source / 'negative-analysis.log', negative)
        receipt['log_sha256'] = sha(analysis)
        receipt['negative_log_sha256'] = sha(negative)
        output = folder / 'compatibility.json'
        output.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
        entry['compatibility'] = {'receipt': str(output.relative_to(PACKAGE)),
                                  'sha256': sha(output),
                                  'log': str(analysis.relative_to(PACKAGE)),
                                  'negative_log': str(negative.relative_to(PACKAGE))}
        entry['negative'] = {'log': str(negative.relative_to(PACKAGE))}
        entry['acquisition'] = {
            'ego_lane': {'entrypoint': 'runner.py',
                         'method': 'original waypoint and body lateral offset at every Native frame',
                         'evidence': 'native-ego-frames.jsonl, video_frames.jsonl'},
            'front_actor': {'entrypoint': 'runner.py',
                            'method': 'independent target-lane front actor pose and surface gap',
                            'evidence': 'native-ego-frames.jsonl, driving-context.json'},
            'rear_actor': {'entrypoint': 'runner.py',
                           'method': 'independent target-lane rear actor pose and surface gap',
                           'evidence': 'native-ego-frames.jsonl, driving-context.json'},
            'observed_indicator': {'entrypoint': 'runner.py',
                                   'method': 'Native vehicle light readback distinct from controller request',
                                   'evidence': 'native-ego-frames.jsonl, four camera views'},
            'controller_check': {'entrypoint': 'runner.py',
                                 'method': 'separate original predeparture check action and sampled actor gap',
                                 'evidence': 'native-driver-checks.jsonl, native-ego-frames.jsonl'},
        }
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'compatibility_bound': len(manifest['cases']),
                      'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
