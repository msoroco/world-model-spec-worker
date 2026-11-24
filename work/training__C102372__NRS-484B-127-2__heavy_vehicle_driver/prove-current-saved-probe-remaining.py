"""Run current saved processing for the remaining probe fallbacks.

This is an unselected synthetic diagnostic, not delivery or Native evidence.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c102372-current-saved-probe-remaining'
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


def main():
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    assert ROOT / '.runtime-work' in output_root.parents
    assert not SCRATCH.exists(), 'Retain previous proof; choose a new scratch name'
    SCRATCH.mkdir(parents=True)
    spec = importlib.util.spec_from_file_location('c102372_probe_package', HERE / 'probe-package.py')
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    from worker_exchange.saved_processing import copy_sources

    manifest = json.loads(MANIFEST.read_text())
    records = []
    for probe in ('probe_1', 'probe_2'):
        case = HERE.name + '__' + probe
        entry = next(c for c in manifest['cases'] if c['case_id'] == case)
        candidates = {c['id']: c for c in entry['candidates']}
        source_build = SCRATCH / probe / 'source-build'
        source_build.mkdir(parents=True)
        source = package.make_source(probe, source_build)
        for candidate in ('fallback2', 'fallback3'):
            attempt = SCRATCH / probe / candidate / 'attempt'
            attempt.parent.mkdir()
            prefix = 'current-saved-' + probe + '-' + candidate
            materialize_log = HERE / (prefix + '-materialize.log')
            code = run([sys.executable, str(ROOT / 'runtime.py'), 'materialize',
                        '--manifest', str(MANIFEST), '--case', case,
                        '--candidate', candidate, '--output', str(attempt)], materialize_log)
            assert code == 0, materialize_log.read_text()[-2000:]
            copy_sources(source, attempt)
            before = files(attempt)
            positive_log = HERE / (prefix + '-process-saved.log')
            output = SCRATCH / probe / candidate / 'processed'
            code = run([sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
                        '--manifest', str(MANIFEST), '--case', case,
                        '--attempt', str(attempt), '--output', str(output),
                        '--library', str(ROOT / 'runtime/pipeline/library'),
                        '--validator', str(VALIDATOR)], positive_log)
            assert code == 0, positive_log.read_text()[-2000:]
            assert files(attempt) == before
            version = output / 'v0001'
            processing = json.loads((version / 'processing.json').read_text())
            analysis = version / 'analysis'
            result = json.loads((analysis / 'result.json').read_text())
            assert processing['passed'] and processing['recorded_only']
            assert processing['candidate_id'] == candidate
            assert processing['analysis_revision']['construction_sha256'] == candidates[candidate]['construction_sha256']
            assert processing['timestamp_joins']['frames'] == 600
            assert processing['originals_preserved'] and not processing['missing_evidence']
            assert result['provenance_kind'] == 'synthetic_cpu' and result['accepted'] is False
            assert result['video_references'] == [
                'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv']
            assert not (attempt / 'channels').exists()
            for name in ('ego_body_pose', 'lead_body_pose', 'surface_gap_m', 'camera_frame_join'):
                assert len((analysis / 'channels' / (name + '.jsonl')).read_text().splitlines()) == 600
            assert (version / 'final-decode.json').is_file()
            records.append({
                'case_id': case, 'candidate_id': candidate,
                'construction_sha256': candidates[candidate]['construction_sha256'],
                'materialize_log_sha256': sha(materialize_log),
                'positive_log_sha256': sha(positive_log),
                'processing_sha256': sha(version / 'processing.json'),
                'analysis_result_sha256': sha(analysis / 'result.json'),
                'final_decode_sha256': sha(version / 'final-decode.json'),
                'original_files_preserved': True, 'source_channels_rebuilt': True,
            })
    receipt = {
        'format': 'c102372-current-saved-probe-remaining-v1',
        'manifest_sha256': sha(MANIFEST), 'frames': 600, 'rate_hz': 20,
        'candidates': records, 'physical_observation_claimed': False,
        'selected_delivery_claimed': False,
    }
    proof = HERE / 'current-saved-probe-remaining-proof.json'
    proof.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'candidates_passed': len(records), 'proof_sha256': sha(proof)}))


if __name__ == '__main__':
    main()
