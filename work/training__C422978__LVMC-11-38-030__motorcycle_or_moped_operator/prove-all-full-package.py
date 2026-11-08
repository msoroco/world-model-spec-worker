"""Run all eight exact unselected C422978 synthetic Core/Lean/video probes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from importlib.machinery import SourceFileLoader


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove():
    os.environ['PATH'] = str(ROOT / '.runtime-work/linux_arm64') + os.pathsep + os.environ.get('PATH', '')
    os.environ['LD_LIBRARY_PATH'] = str(ROOT / '.runtime-work/geos-wheel/shapely.libs') + os.pathsep + os.environ.get('LD_LIBRARY_PATH', '')
    manifest_path = HERE / 'draft-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    scratch = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c422978-full-batch-'))
    media = scratch / 'media'
    media.mkdir()
    shutil.copyfile(HERE / 'native/saved-fixtures/witness_1/primary/video_frames.jsonl',
                    media / 'video_frames.jsonl')
    module = SourceFileLoader('c422978_full_probe', str(HERE / 'probe-full-package.py')).load_module()
    module.make_media(media)
    results = []
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            folder = HERE / 'draft-candidates' / case / candidate
            cmd = [str(ROOT / '.venv-cpu/bin/python'), str(HERE / 'probe-full-package.py'),
                   '--case', case, '--candidate', candidate,
                   '--media-source', str(media)]
            run = subprocess.run(cmd, cwd=ROOT, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
            (folder / 'full-package-command.log').write_text(run.stdout)
            if run.returncode:
                raise ValueError(f'{case}/{candidate}: {run.stdout[-1800:]}')
            proof = json.loads((folder / 'full-package-proof.json').read_text())
            selected = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            assert proof['construction_sha256'] == selected['construction_sha256']
            results.append(proof)
            print(case, candidate, 'full positive and missing-source negative passed', flush=True)
    summary = {'format': 'c422978-exact-full-package-summary-v1',
               'manifest_sha256': sha(manifest_path), 'results': results,
               'original_native_or_delivery_acceptance_claimed': False}
    (HERE / 'full-package-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    print(json.dumps({'results': len(prove()['results'])}))
