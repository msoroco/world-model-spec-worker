"""Execute each exact bundled saved meter on synthetic local packets."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize, execution_env

MANIFEST = FOLDER / 'draft-execution-manifest.json'
SOURCES = ('native-observed.jsonl', 'native-map-readback.json',
           'video_frames.jsonl', 'capture/evidence.jsonl')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_sources(case, candidate, bundle):
    source = FOLDER / 'native/saved-fixtures' / case / candidate
    for name in SOURCES:
        target = bundle / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)


def invoke(bundle):
    return subprocess.run([sys.executable, str(bundle / 'measure_saved.py'), str(bundle)],
                          cwd=bundle, env=execution_env(), text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)


def prove():
    manifest = json.loads(MANIFEST.read_text())
    scratch = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c422978-saved-package-'))
    results = []
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            bundle = scratch / (case + '-' + candidate)
            materialize(MANIFEST, entry['case_id'], bundle, candidate)
            copy_sources(case, candidate, bundle)
            run = invoke(bundle)
            if run.returncode:
                raise ValueError(f'{case}/{candidate}: bundled meter failed: {run.stdout[-1000:]}')
            result = json.loads(run.stdout)
            assert result['frames'] == 480 and result['source_kind'] == 'synthetic_cpu'
            assert bool(result['moving_sidewalk_overlap_frames']) == (case == 'witness_2')
            assert result['legal_verdict'] is None and not result['city_sidewalk_verified']
            bad = scratch / (case + '-' + candidate + '-missing')
            materialize(MANIFEST, entry['case_id'], bad, candidate)
            copy_sources(case, candidate, bad)
            (bad / 'native-observed.jsonl').unlink()
            failure = invoke(bad)
            expected = 'Missing required source: native-observed.jsonl'
            if failure.returncode == 0 or expected not in failure.stdout:
                raise ValueError(f'{case}/{candidate}: deleted source accepted')
            output = FOLDER / 'draft-candidates' / case / candidate
            (output / 'saved-package-positive.json').write_text(json.dumps(result, indent=2) + '\n')
            (output / 'saved-package-negative.log').write_text(failure.stdout)
            ref = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            row = {'case_id': entry['case_id'], 'candidate_id': candidate,
                   'construction_sha256': ref['construction_sha256'],
                   'positive_sha256': sha(output / 'saved-package-positive.json'),
                   'negative_log_sha256': sha(output / 'saved-package-negative.log'),
                   'negative_error': expected}
            results.append(row)
            print(case, candidate, 'positive and source-removal negative passed', flush=True)
    proof = {'format': 'c422978-exact-saved-package-proof-v1',
             'manifest_sha256': sha(MANIFEST), 'results': results,
             'original_native_or_delivery_acceptance_claimed': False}
    (FOLDER / 'exact-saved-package-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    return proof


if __name__ == '__main__':
    print(json.dumps({'results': len(prove()['results'])}))
