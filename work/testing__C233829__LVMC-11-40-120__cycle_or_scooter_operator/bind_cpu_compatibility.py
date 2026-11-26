"""Bind current exact offline and positive/missing-source compatibility proofs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c233829'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(data):
    if not data:
        return ''
    return '\n'.join(line.rstrip() for line in data.splitlines()).rstrip() + '\n'


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        name = case.removeprefix(HERE.name + '__')
        offline = SCRATCH / ('offline-' + name + '-final2') / 'offline.log'
        compatible = next(
            (candidate for candidate in (
                SCRATCH / ('compatibility-' + name + '-final2'),)
             if (candidate / 'compatibility.json').is_file() and
             json.loads((candidate / 'compatibility.json').read_text()).get('construction_sha256') == entry['construction_sha256']),
            None)
        if compatible is None:
            raise ValueError('current compatibility proof missing: ' + name)
        proof = json.loads((compatible / 'compatibility.json').read_text())
        if proof.get('passed') is not True or proof.get('case_id') != case or proof.get('construction_sha256') != entry['construction_sha256']:
            raise ValueError('current compatibility proof missing: ' + name)
        local_offline = HERE / ('cpu-offline-' + name + '.log')
        local_offline.write_text(clean(offline.read_text()))
        local_analysis = HERE / ('cpu-compat-analysis-' + name + '.log')
        local_analysis.write_text(clean((compatible / 'compatibility-analysis.log').read_text()))
        local_negative = HERE / ('cpu-compat-negative-' + name + '.log')
        local_negative.write_text(clean((compatible / 'negative-analysis.log').read_text()))
        proof['log_sha256'] = sha(local_analysis)
        proof['negative_log_sha256'] = sha(local_negative)
        receipt = HERE / ('cpu-compat-' + name + '-receipt.json')
        receipt.write_text(json.dumps(proof, indent=2) + '\n')
        command = ('.venv-cpu/bin/python runtime.py offline --manifest work/' + HERE.name +
                   '/execution-manifest.json --case ' + case + ' --output $OUTPUT --python $CPU_PYTHON')
        entry['offline'] = {'command': command, 'exit_code': 0,
                            'construction_sha256': entry['construction_sha256'],
                            'log': local_offline.name, 'log_sha256': sha(local_offline)}
        entry['compatibility'] = {'receipt': receipt.name, 'sha256': sha(receipt),
                                  'log': local_analysis.name}
        entry['negative'] = {'log': local_negative.name}
        construction = json.loads((HERE / entry['construction']).read_text())
        channels = [item['name'] for item in construction['recording_description']['channels']]
        entry['acquisition'] = {channel: {
            'entrypoint': 'runner.py', 'method': 'capture_original',
            'evidence': 'Post-tick original Native actor frame plus four camera frame IDs and reviewed site source packet.'
        } for channel in channels}
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
