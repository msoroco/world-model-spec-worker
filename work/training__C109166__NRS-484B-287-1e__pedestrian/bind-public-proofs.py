"""Bind exact offline and diagnostic compatibility proofs without changing sources."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def bind():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for suffix in ('controlled_1', 'controlled_2'):
        entry = next(e for e in manifest['cases'] if e['case_id'] == BASE + '__' + suffix)
        for candidate in ('primary', 'fallback1'):
            selected = entry if candidate == 'primary' else entry['candidates'][0]
            directory = HERE / 'cases' / suffix / candidate
            offline_log = HERE / f'selected-{suffix[-1]}-{candidate}-offline.log'
            if 'offline_passed' not in offline_log.read_text():
                raise ValueError('Exact offline proof absent: ' + suffix + '/' + candidate)
            selected['offline'] = {
                'exit_code': 0, 'construction_sha256': selected['construction_sha256'],
                'command': f'runtime.py offline --case {entry["case_id"]} --candidate {candidate}',
                'log': str(offline_log.relative_to(HERE)),
                'log_sha256': sha(offline_log)}
            label = suffix + '-' + candidate
            public_log = HERE / ('public-' + label + '.log')
            receipt = json.loads(public_log.read_text())
            if (receipt.get('passed') is not True or receipt['case_id'] != entry['case_id']
                    or receipt['candidate_id'] != candidate
                    or receipt['construction_sha256'] != selected['construction_sha256']):
                raise ValueError('Public receipt identity differs: ' + label)
            output_name = 'c109166-public-r5-' + label
            output = ROOT / '.runtime-work' / output_name
            analysis = directory / 'public-analysis.log'
            negative = directory / 'negative-analysis.log'
            shutil.copyfile(output / 'compatibility-analysis.log', analysis)
            shutil.copyfile(output / 'negative-analysis.log', negative)
            if sha(analysis) != receipt['log_sha256'] or sha(negative) != receipt['negative_log_sha256']:
                raise ValueError('Public receipt logs differ: ' + label)
            receipt_path = directory / 'public-receipt.json'
            write(receipt_path, receipt)
            selected['compatibility'] = {
                'receipt': str(receipt_path.relative_to(HERE)), 'sha256': sha(receipt_path),
                'log': str(analysis.relative_to(HERE)),
                'negative_log': str(negative.relative_to(HERE))}
    write(manifest_path, manifest)
    print(json.dumps({'bound_candidates': 4, 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    bind()
