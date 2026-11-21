"""Bind current JSON adapter compatibility receipts to exact selected cases."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('_', 1)[-1]
        letter = {'a': 'a', 'b': 'b'}[suffix]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            run_name = f'c110741-update162-{letter}-{candidate}-compat'
            if letter == 'a' and candidate == 'primary':
                run_name += '-v2'
            generated = ROOT / '.runtime-work' / run_name
            proof = json.loads((generated / 'compatibility.json').read_text())
            construction = entry if candidate == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate)
            if (proof['passed'] is not True or proof['case_id'] != entry['case_id']
                    or proof['candidate_id'] != candidate
                    or proof['construction_sha256'] != construction['construction_sha256']
                    or proof['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256']):
                raise ValueError('Generated receipt does not match selected construction')
            paths = {
                'receipt': ('compatibility.json', f'update162-{letter}-{candidate}-compatibility.json'),
                'log': ('compatibility-analysis.log', f'update162-{letter}-{candidate}-analysis.log'),
                'negative_log': ('negative-analysis.log', f'update162-{letter}-{candidate}-negative.log'),
                'report': ('analysis-report.json', f'update162-{letter}-{candidate}-report.json'),
                'decode': ('final-decode.json', f'update162-{letter}-{candidate}-decode.json'),
            }
            for source_name, target_name in paths.values():
                shutil.copyfile(generated / source_name, HERE / target_name)
            if sha(HERE / paths['log'][1]) != proof['log_sha256'] or \
                    sha(HERE / paths['negative_log'][1]) != proof['negative_log_sha256']:
                raise ValueError('Positive or negative source log changed')
            construction['compatibility'] = {
                'receipt': paths['receipt'][1],
                'sha256': sha(HERE / paths['receipt'][1]),
                'log': paths['log'][1],
                'negative_log': paths['negative_log'][1],
            }
            if candidate == 'primary':
                entry['negative']['log'] = paths['negative_log'][1]
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    return {'case_count': len(manifest['cases']), 'candidate_count': 8,
            'manifest_sha256': sha(MANIFEST)}


if __name__ == '__main__':
    print(json.dumps(bind(), indent=2))
