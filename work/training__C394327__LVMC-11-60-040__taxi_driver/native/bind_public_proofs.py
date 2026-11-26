"""Bind four selected public compatibility diagnostics to the taxi draft."""
import hashlib
import json
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
PREFIX = BASE.name
SUFFIXES = ('probe_a', 'probe_b')
CANDIDATES = ('primary', 'fallback1')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = BASE / 'selected-draft-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for suffix in SUFFIXES:
        entry = next(e for e in manifest['cases']
                     if e['case_id'] == PREFIX + '__' + suffix)
        for candidate in CANDIDATES:
            item = entry if candidate == 'primary' else entry['candidates'][0]
            source = (ROOT / '.runtime-work' /
                      ('c394327-public-' + suffix + '-' + candidate + '-road-v10'))
            receipt = json.loads((source / 'compatibility.json').read_text())
            expected = {'case_id': entry['case_id'], 'candidate_id': candidate,
                        'construction_sha256': item['construction_sha256'],
                        'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}
            if any(receipt.get(k) != v for k, v in expected.items()):
                raise ValueError('Public receipt binding differs: ' + suffix + ':' + candidate)
            if receipt.get('passed') is not True:
                raise ValueError('Public compatibility did not pass')
            dest = BASE / 'native' / 'public' / suffix / candidate
            dest.mkdir(parents=True, exist_ok=True)
            names = {'compatibility.json': 'compatibility.json',
                     'compatibility-analysis.log': 'analysis.log',
                     'negative-analysis.log': 'missing-source.log'}
            for source_name, target_name in names.items():
                shutil.copyfile(source / source_name, dest / target_name)
                old = dest / source_name
                if old != dest / target_name and old.is_file():
                    old.unlink()
            if sha(dest / 'analysis.log') != receipt['log_sha256']:
                raise ValueError('Public positive analysis log changed')
            if sha(dest / 'missing-source.log') != receipt['negative_log_sha256']:
                raise ValueError('Public negative analysis log changed')
            rel = dest.relative_to(BASE)
            item['compatibility'] = {
                'receipt': str(rel / 'compatibility.json'),
                'sha256': sha(dest / 'compatibility.json'),
                'log': str(rel / 'analysis.log'),
                'negative_log': str(rel / 'missing-source.log')}
            item['negative'] = {
                'log': str(rel / 'missing-source.log'),
                'log_sha256': sha(dest / 'missing-source.log')}
            saved_root = ROOT / '.runtime-work' / (
                'c394327-saved-' + suffix + '-' + candidate + '-v10')
            saved = json.loads((saved_root / 'v0001' / 'processing.json').read_text())
            if (saved.get('case_id') != entry['case_id'] or
                    saved.get('candidate_id') != candidate or
                    saved.get('passed') is not True or
                    saved.get('recorded_only') is not True or
                    saved.get('originals_preserved') is not True or
                    saved.get('missing_evidence') is not False):
                raise ValueError('Saved processing proof differs: ' + suffix + ':' + candidate)
            saved_dest = BASE / 'native' / 'saved' / suffix / candidate
            saved_dest.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(saved_root / 'v0001' / 'processing.json',
                            saved_dest / 'processing.json')
            saved_log = ROOT / '.runtime-work' / 'lead-current-audits' / (
                'c394327-saved-' + suffix + '-' + candidate + '-v10.log')
            shutil.copyfile(saved_log, saved_dest / 'saved.log')
            saved_rel = saved_dest.relative_to(BASE)
            item['saved_cpu_proof'] = {
                'receipt': str(saved_rel / 'processing.json'),
                'sha256': sha(saved_dest / 'processing.json'),
                'log': str(saved_rel / 'saved.log'),
                'log_sha256': sha(saved_dest / 'saved.log')}
            if candidate == 'primary':
                entry['post_capture'] = {
                    'recorded_only': True,
                    'command': ('runtime.py process-saved --manifest work/' + PREFIX +
                                '/selected-draft-manifest.json --case ' + entry['case_id'] +
                                ' --attempt $ATTEMPT --output $SAVED_OUTPUT' +
                                ' --library runtime/library --validator $DECODER'),
                    'feedback_command': 'cat $SAVED_OUTPUT/feedback.json',
                    'test_exit_code': 0,
                    'test_log': str(saved_rel / 'saved.log'),
                    'test_log_sha256': sha(saved_dest / 'saved.log')}
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
