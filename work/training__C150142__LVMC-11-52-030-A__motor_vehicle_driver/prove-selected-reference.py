"""Pinned short-case CPU compatibility and saved-processing proof."""
import hashlib
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
DEFAULT_MANIFEST = ROOT / 'execution-manifest-draft-all.json'
PYTHON = REPO / '.venv-cpu/bin/python'
VALIDATOR = REPO / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as materialize_fixture
from worker_exchange.saved_processing import copy_sources


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args, log):
    with log.open('w') as output:
        result = subprocess.run([str(PYTHON), *map(str, args)], cwd=REPO,
                                stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(str(args[:2]) + ' failed: ' + str(log) +
                           '\n' + log.read_text()[-1200:])
    return json.loads(log.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--tag', default='v3')
    parser.add_argument('--slug', choices=('reference', 'contrast',
                                            'ordinary_red_signed',
                                            'mail_adjacent_deposit',
                                            'mail_no_box_deposit'),
                        default='reference')
    parser.add_argument('--candidates', nargs='+',
                        choices=('primary', 'fallback1', 'fallback2', 'fallback3'),
                        default=('primary', 'fallback1', 'fallback2', 'fallback3'))
    args = parser.parse_args()
    if not args.tag.replace('-', '').isalnum():
        raise ValueError('Tag must be a simple output label')
    manifest_path = args.manifest.resolve()
    case_id = ROOT.name + '__' + args.slug
    manifest = json.loads(manifest_path.read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'] == case_id)
    records = []
    for candidate in args.candidates:
        chosen = entry if candidate == 'primary' else next(
            c for c in entry['candidates'] if c['id'] == candidate)
        construction = json.loads((ROOT / chosen['construction']).read_text())
        config = json.loads(next(f['content'] for f in construction['files']
                                 if f['path'] == 'config.json'))
        expected_frames = config.get('capture_frames', config.get('frames'))
        prefix = REPO / '.runtime-work' / ('c150142-selected-' + args.slug + '-' + candidate + '-' + args.tag)
        compat_dir = Path(str(prefix) + '-compat')
        compat_log = Path(str(prefix) + '-compat.full.log')
        compat = run([REPO / 'runtime.py', 'compatibility',
                      '--manifest', manifest_path, '--case', case_id,
                      '--candidate', candidate, '--output', compat_dir,
                      '--library', REPO / 'runtime/pipeline/library',
                      '--validator', VALIDATOR], compat_log)
        attempt = Path(str(prefix) + '-attempt')
        fixture = Path(str(prefix) + '-fixture')
        result_dir = Path(str(prefix) + '-result')
        saved_log = Path(str(prefix) + '-process.full.log')
        materialize(manifest_path, case_id, attempt, candidate)
        recipe = REPO / entry['fixture_recipe']
        fixture_receipt = materialize_fixture(REPO, recipe, fixture)
        copy_sources(fixture, attempt)
        saved = run([REPO / 'runtime.py', 'process-saved',
                     '--manifest', manifest_path, '--case', case_id,
                     '--attempt', attempt, '--output', result_dir,
                     '--library', REPO / 'runtime/pipeline/library',
                     '--validator', VALIDATOR], saved_log)
        if (compat['passed'] is not True or saved['passed'] is not True or
                compat['case_id'] != saved['case_id'] or
                compat['candidate_id'] != saved['candidate_id'] or
                compat['construction_sha256'] != chosen['construction_sha256'] or
                saved['timestamp_joins']['frames'] != expected_frames or
                saved['final_video_checks']['frames'] != expected_frames or
                saved['physical_acceptance_claimed'] or
                saved['legal_acceptance_claimed']):
            raise ValueError('Selected short-case compatibility/saved proof mismatch')
        records.append({'case_id': case_id, 'candidate_id': candidate,
                        'manifest_sha256': sha(manifest_path),
                        'construction_sha256': chosen['construction_sha256'],
                        'fixture_sha256': fixture_receipt['fixture_sha256'],
                        'compatibility_receipt_sha256': sha(compat_dir / 'compatibility.json'),
                        'compatibility_negative_log_sha256': compat['negative_log_sha256'],
                        'saved_result_sha256': sha(saved_log),
                        'saved_frames': saved['timestamp_joins']['frames'],
                        'source_kind': 'synthetic_native_sample',
                        'physical_acceptance_claimed': False})
        print(candidate, 'compatibility and saved processing passed', flush=True)
    target = ROOT / ('selected-' + args.slug + '-four-candidate-proof-' + args.tag + '.json')
    target.write_text(json.dumps({'format': 'selected-short-case-cpu-diagnostic',
                                  'records': records, 'selected_case_id': case_id,
                                  'original_native_observed': False}, indent=2) + '\n')
    print(target.relative_to(REPO))


if __name__ == '__main__':
    main()
