"""Bind exact final construction hashes to completed pinned CPU receipts."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'selected-probe-manifest.json'
SCRATCH = REPO / '.runtime-work'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    proofs = ROOT / 'selected-proofs'
    proofs.mkdir(exist_ok=True)
    for case in manifest['cases']:
        suffix = case['case_id'].rsplit('__', 1)[-1]
        for candidate_id, item in [('primary', case)] + [(c['id'], c) for c in case['candidates']]:
            stem = suffix + '-' + candidate_id
            offline_dir = SCRATCH / ('c234827-nrs-' + stem + '-offline-final')
            compat_dir = SCRATCH / ('c234827-nrs-' + stem +
                                   ('-compat2' if stem == 'reference-primary' else '-compat3'))
            for source, dest in ((offline_dir / 'offline.log', ROOT / ('selected-' + stem + '-offline.log')),
                                 (compat_dir / 'compatibility.json', proofs / (stem + '-compatibility.json')),
                                 (compat_dir / 'compatibility-analysis.log', proofs / (stem + '-analysis.log')),
                                 (compat_dir / 'negative-analysis.log', proofs / (stem + '-negative.log'))):
                shutil.copyfile(source, dest)
            receipt = json.loads((proofs / (stem + '-compatibility.json')).read_text())
            if not receipt['passed'] or receipt['construction_sha256'] != item['construction_sha256']:
                raise ValueError('Selected receipt differs from construction: ' + stem)
            item['offline'] = {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + ROOT.name +
                           '/selected-probe-manifest.json --case ' + case['case_id'] +
                           ' --candidate ' + candidate_id +
                           ' --output .runtime-work/c234827-nrs-' + stem +
                           '-offline-final --python $PWD/.venv-cpu/bin/python',
                'exit_code': 0, 'construction_sha256': item['construction_sha256'],
                'log': 'selected-' + stem + '-offline.log',
                'log_sha256': sha(ROOT / ('selected-' + stem + '-offline.log'))}
            item['compatibility'] = {'receipt': 'selected-proofs/' + stem + '-compatibility.json',
                                     'sha256': sha(proofs / (stem + '-compatibility.json')),
                                     'log': 'selected-proofs/' + stem + '-analysis.log',
                                     'negative_log': 'selected-proofs/' + stem + '-negative.log'}
            item['negative'] = {'log': 'selected-proofs/' + stem + '-negative.log'}
        saved = SCRATCH / ('c234827-nrs-' + suffix + '-saved-output/v0001/processing.json')
        if saved.is_file():
            dest = proofs / (suffix + '-primary-processing.json')
            shutil.copyfile(saved, dest)
            processing = json.loads(dest.read_text())
            if not (processing['passed'] and processing['recorded_only'] and
                    processing['originals_preserved'] and processing['timestamp_joins']['passed']):
                raise ValueError('Saved receipt incomplete: ' + suffix)
            case['saved_processing'] = {'receipt': 'selected-proofs/' + dest.name,
                                        'sha256': sha(dest)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'candidates_bound': 4, 'manifest_sha256': sha(MANIFEST)}))


if __name__ == '__main__':
    main()
