"""Exercise every exact unselected bundle with saved CPU packets and negatives."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
sys.path.insert(0, str(FOLDER / 'native'))
from worker_exchange.runtime_cli import materialize, execution_env
from prove_saved import packet, save

MANIFEST = FOLDER / 'draft-execution-manifest.json'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def invoke(bundle):
    return subprocess.run([sys.executable, str(bundle / 'measure_saved.py'), str(bundle)],
                          cwd=bundle, env=execution_env(), text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)


def prove():
    manifest = json.loads(MANIFEST.read_text())
    output = {'format': 'c405647-1b-exact-saved-package-proof-v1',
              'draft_manifest_sha256': sha(MANIFEST), 'results': [],
              'physical_or_legal_acceptance_claimed': False,
              'full_core_video_compatibility_claimed': False}
    scratch = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c405647-1b-saved-package-'))
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in CANDIDATES:
            bundle = scratch / (case + '-' + candidate)
            materialize(MANIFEST, entry['case_id'], bundle, candidate)
            scope, actors = packet(case, candidate)
            save(bundle, scope, actors)
            positive = invoke(bundle)
            if positive.returncode:
                raise ValueError(f'{case}/{candidate}: exact positive failed: {positive.stdout[-1000:]}')
            measured = json.loads(positive.stdout)
            if (measured['source_kind'] != 'synthetic_cpu' or measured['frames'] != 480 or
                    measured['edge_before_catchup'] != (case == 'reference') or
                    measured['legal_immediacy_or_edge_verdict'] is not None):
                raise ValueError(f'{case}/{candidate}: exact saved measurement differs')
            negative = scratch / (case + '-' + candidate + '-missing-source')
            materialize(MANIFEST, entry['case_id'], negative, candidate)
            save(negative, scope, actors)
            (negative / 'actor-frames.jsonl').unlink()
            missing = invoke(negative)
            if missing.returncode == 0 or 'saved source files absent' not in missing.stdout:
                raise ValueError(f'{case}/{candidate}: missing source accepted')
            retained = FOLDER / 'draft-candidates' / case / candidate
            positive_log = retained / 'saved-package-positive.json'
            negative_log = retained / 'saved-package-negative.log'
            positive_log.write_text(positive.stdout)
            negative_log.write_text(missing.stdout)
            selected = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            output['results'].append({
                'case_id': entry['case_id'], 'candidate_id': candidate,
                'construction_sha256': selected['construction_sha256'],
                'bundle_measure_saved_sha256': sha(bundle / 'measure_saved.py'),
                'scope_sha256': measured['scope_sha256'],
                'actor_frames_sha256': measured['actor_frames_sha256'],
                'edge_frame': measured['first_edge_target_frame'],
                'catchup_frame': measured['approach_catchup_frame'],
                'positive_exit_code': positive.returncode,
                'positive_log': str(positive_log.relative_to(FOLDER)),
                'positive_log_sha256': sha(positive_log),
                'missing_source_exit_code': missing.returncode,
                'missing_source_error': 'saved source files absent',
                'negative_log': str(negative_log.relative_to(FOLDER)),
                'negative_log_sha256': sha(negative_log)})
            print(case, candidate, 'exact saved package positive and negative passed', flush=True)
    if len(output['results']) != 8:
        raise ValueError('Expected eight exact bundles')
    target = FOLDER / 'exact-saved-package-proof.json'
    target.write_text(json.dumps(output, indent=2) + '\n')
    return output


if __name__ == '__main__':
    result = prove()
    print(json.dumps({'results': len(result['results']),
                      'proof_sha256': sha(FOLDER / 'exact-saved-package-proof.json')}))
