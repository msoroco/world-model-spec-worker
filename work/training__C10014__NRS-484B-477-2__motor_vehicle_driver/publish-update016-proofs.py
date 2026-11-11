"""Retain small current CPU receipts from ignored exact diagnostic attempts."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def locations(suffix, candidate):
    attempt = ROOT/'.runtime-work'/f'c10014-update016-{suffix}-{candidate}-compat'
    saved = ROOT/'.runtime-work'/f'c10014-update016-{suffix}-{candidate}-saved/v0001'
    return attempt, saved


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if target.stat().st_size >= 2*1024*1024:
        raise ValueError('Proof exceeds worker text-file limit: '+str(target))
    return {'path': target.relative_to(HERE).as_posix(), 'sha256': sha(target)}


def publish():
    manifest = json.loads((HERE/'draft-execution-manifest.json').read_text())
    proofs = []
    for suffix, entry in zip(('reference', 'contrast'), manifest['cases']):
        if not entry['case_id'].endswith('__'+suffix):
            raise ValueError('Draft exact case order changed')
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            selected = entry if candidate == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate)
            attempt, saved = locations(suffix, candidate)
            receipt = json.loads((attempt/'compatibility.json').read_text())
            processing = json.loads((saved/'processing.json').read_text())
            if (receipt.get('passed') is not True or
                    receipt.get('case_id') != entry['case_id'] or
                    receipt.get('candidate_id') != candidate or
                    receipt.get('construction_sha256') != selected['construction_sha256'] or
                    processing.get('passed') is not True or
                    processing.get('case_id') != entry['case_id'] or
                    processing.get('candidate_id') != candidate or
                    processing.get('originals_preserved') is not True):
                raise ValueError('Current proof identity or result differs')
            target = HERE/'update016-proofs'/suffix/candidate
            files = [copy(attempt/source, target/destination) for source, destination in (
                ('compatibility.json', 'compatibility.json'),
                ('compatibility-analysis.log', 'analysis.log'),
                ('negative-analysis.log', 'negative-analysis.log'))]
            files += [copy(saved/source, target/destination) for source, destination in (
                ('processing.json', 'saved-processing.json'),
                ('analysis.log', 'saved-analysis.log'))]
            proofs.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                           'construction_sha256': selected['construction_sha256'],
                           'files': files})
    index = {'format': 'c10014-update016-current-cpu-proof-index',
             'draft_manifest_sha256': sha(HERE/'draft-execution-manifest.json'),
             'proofs': proofs,
             'scope': 'unselected synthetic compatibility and saved processing; no Native or legal acceptance'}
    (HERE/'update016-proof-index.json').write_text(json.dumps(index, indent=2)+'\n')
    print(json.dumps({'passed': True, 'candidates': len(proofs),
                      'manifest_sha256': index['draft_manifest_sha256']}))


if __name__ == '__main__':
    publish()
