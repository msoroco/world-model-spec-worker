"""Exercise exact unselected probe_2 primary and fallback1 through process-saved."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c102372-current-saved-pair'
CASE = HERE.name + '__probe_2'
MANIFEST = HERE / 'draft-execution-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(path):
    return {p.relative_to(path).as_posix(): sha(p) for p in path.rglob('*') if p.is_file()}


def run(cmd, log):
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    log.write_text(result.stdout + result.stderr)
    return result.returncode


def process(attempt, output, log):
    return run([sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
                '--manifest', str(MANIFEST), '--case', CASE, '--attempt', str(attempt),
                '--output', str(output), '--library', str(ROOT / 'runtime/pipeline/library'),
                '--validator', str(VALIDATOR)], log)


def main():
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    assert ROOT / '.runtime-work' in output_root.parents
    assert not SCRATCH.exists(), 'Retain previous proof; choose a new scratch name'
    SCRATCH.mkdir(parents=True)
    spec = importlib.util.spec_from_file_location('c102372_probe_package', HERE / 'probe-package.py')
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    source_build = SCRATCH / 'source-build'
    source_build.mkdir()
    source = package.make_source('probe_2', source_build)
    manifest = json.loads(MANIFEST.read_text())
    entry = next(c for c in manifest['cases'] if c['case_id'] == CASE)
    candidates = {'primary': entry, **{c['id']: c for c in entry['candidates']}}
    from worker_exchange.saved_processing import copy_sources
    records = []
    for candidate in ('primary', 'fallback1'):
        attempt = SCRATCH / candidate / 'attempt'
        attempt.parent.mkdir()
        materialize_log = HERE / f'current-saved-pair-{candidate}-materialize.log'
        code = run([sys.executable, str(ROOT / 'runtime.py'), 'materialize',
                    '--manifest', str(MANIFEST), '--case', CASE, '--candidate', candidate,
                    '--output', str(attempt)], materialize_log)
        assert code == 0, materialize_log.read_text()[-2000:]
        copy_sources(source, attempt)
        before = files(attempt)
        log = HERE / f'current-saved-pair-{candidate}.log'
        code = process(attempt, SCRATCH / candidate / 'processed', log)
        assert code == 0, log.read_text()[-2000:]
        assert files(attempt) == before
        version = SCRATCH / candidate / 'processed/v0001'
        processing = json.loads((version / 'processing.json').read_text())
        analysis = version / 'analysis'
        result = json.loads((analysis / 'result.json').read_text())
        assert processing['passed'] and processing['recorded_only']
        assert processing['candidate_id'] == candidate
        assert processing['analysis_revision']['construction_sha256'] == candidates[candidate]['construction_sha256']
        assert processing['timestamp_joins']['frames'] == 600
        assert processing['originals_preserved'] and not processing['missing_evidence']
        assert result['provenance_kind'] == 'synthetic_cpu' and result['accepted'] is False
        assert result['video_references'] == ['overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv']
        assert not (attempt / 'channels').exists()
        for name in ('ego_body_pose', 'lead_body_pose', 'surface_gap_m', 'camera_frame_join'):
            assert len((analysis / 'channels' / f'{name}.jsonl').read_text().splitlines()) == 600
        assert (version / 'final-decode.json').is_file()
        records.append({'candidate_id': candidate, 'construction_sha256': candidates[candidate]['construction_sha256'],
                        'materialize_log_sha256': sha(materialize_log), 'positive_log_sha256': sha(log),
                        'processing_sha256': sha(version / 'processing.json'),
                        'analysis_result_sha256': sha(analysis / 'result.json'),
                        'final_decode_sha256': sha(version / 'final-decode.json'),
                        'original_files_preserved': True, 'source_channels_rebuilt': True})
    attempt = SCRATCH / 'fallback1/attempt'
    tampered = SCRATCH / 'fallback1/tampered-attempt'
    shutil.copytree(attempt, tampered, copy_function=os.link)
    receipt = tampered / 'candidate-selection.json'
    value = json.loads(receipt.read_text())
    value['construction_sha256'] = candidates['primary']['construction_sha256']
    receipt.unlink()
    receipt.write_text(json.dumps(value, sort_keys=True) + '\n')
    before = files(tampered)
    negative_log = HERE / 'current-saved-pair-candidate-negative.log'
    code = process(tampered, SCRATCH / 'fallback1/negative-processed', negative_log)
    assert code != 0 and files(tampered) == before
    feedback = json.loads((SCRATCH / 'fallback1/negative-processed/v0001/feedback.json').read_text())
    assert 'candidate identity differs from frozen manifest' in feedback['error']
    assert feedback['native_replay_requested'] is False
    receipt = {'format': 'c102372-current-saved-pair-v1', 'case_id': CASE,
               'manifest_sha256': sha(MANIFEST), 'frames': 600, 'rate_hz': 20,
               'candidates': records, 'negative_exit_code': code,
               'negative_log_sha256': sha(negative_log),
               'negative_feedback_sha256': sha(SCRATCH / 'fallback1/negative-processed/v0001/feedback.json'),
               'negative_error': feedback['error'], 'native_replay_requested': False,
               'physical_observation_claimed': False, 'selected_delivery_claimed': False}
    (HERE / 'current-saved-pair-proof.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'candidates_passed': 2, 'negative_rejected': True,
                      'proof_sha256': sha(HERE / 'current-saved-pair-proof.json')}))


if __name__ == '__main__':
    main()
