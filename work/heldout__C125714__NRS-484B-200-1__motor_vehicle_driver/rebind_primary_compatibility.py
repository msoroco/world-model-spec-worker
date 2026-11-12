"""Rerun exact primary saved-processing proofs and retain textual receipts."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
MANIFESTS = {
    'baseline_right_east': 'probe-compatibility-manifest.json',
    'baseline_right_west': 'probe-compatibility-west-manifest.json',
    'unexcepted_left': 'probe-compatibility-left-manifest.json',
    'right_half_closed': 'probe-compatibility-closure-manifest.json',
    'passing_same_direction': 'probe-compatibility-passing-manifest.json',
    'insufficient_width': 'probe-compatibility-narrow-manifest.json',
    'posted_one_way': 'probe-compatibility-one-way-manifest.json',
    'three_lane': 'probe-compatibility-three-lane-manifest.json',
}


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    bound = {}
    for suffix, source in MANIFESTS.items():
        case = AID + '__' + suffix
        output = ROOT / '.runtime-work' / ('c125714-canonical-' + suffix + '-' + str(time.time_ns()))
        command = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                   '--manifest', str(HERE / source), '--case', case,
                   '--output', str(output), '--library', str(ROOT / 'runtime/library'),
                   '--validator', str(ROOT / '.runtime-work/c125714-validator/.lake/build/bin/adapterCheck')]
        log = HERE / ('canonical-' + suffix + '-compatibility.log')
        with log.open('w') as stream:
            subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)
        names = {'receipt': 'compatibility.json', 'analysis': 'compatibility-analysis.log',
                 'negative': 'negative-analysis.log'}
        copied = {}
        for kind, name in names.items():
            target = HERE / ('canonical-' + suffix + '-' + name)
            shutil.copyfile(output / name, target)
            copied[kind] = {'path': target.name, 'sha256': digest(target)}
        receipt = json.loads((HERE / copied['receipt']['path']).read_text())
        if (receipt.get('case_id') != case or receipt.get('candidate_id') != 'primary'
                or receipt.get('passed') is not True):
            raise ValueError('Wrong primary compatibility result: ' + case)
        bound[suffix] = {'manifest': source, 'command': ' '.join(command),
                         'driver_log': {'path': log.name, 'sha256': digest(log)},
                         'copied': copied}
        print(suffix, 'primary compatibility passed', flush=True)
    (HERE / 'canonical-primary-compatibility-index.json').write_text(json.dumps(bound, indent=2) + '\n')


if __name__ == '__main__':
    main()
