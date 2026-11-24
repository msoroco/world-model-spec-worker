"""Exercise fresh selected saved processing on diagnostic source fixtures."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
VALIDATOR = REPO / '.runtime-work/c110969-decoder/.lake/build/bin/adapterCheck'
SCRATCH = REPO / '.runtime-work/c110969-saved-proof'
SUFFIXES = ('outside_reference', 'inside_stop', 'inside_stand', 'inside_park',
            'traffic_conflict', 'law_direction', 'officer_direction',
            'device_direction', 'through_motion')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, log):
    proc = subprocess.run(args, cwd=REPO, env=os.environ, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(proc.stdout.rstrip() + '\n')
    if proc.returncode:
        raise RuntimeError(f'{args[2]} failed: {proc.stdout[-1000:]}')
    return proc


def main():
    from worker_exchange.saved_processing import copy_sources
    SCRATCH.mkdir(parents=True, exist_ok=True)
    selected = sha(MANIFEST)
    summary = {'format': 'c110969-diagnostic-saved-proof',
               'scope': 'synthetic source-shaped CPU diagnostic only',
               'selected_manifest_sha256': selected, 'cases': []}
    for suffix in SUFFIXES:
        case = ROOT.name + '__' + suffix
        tag = uuid.uuid4().hex[:12]
        base = SCRATCH / (suffix + '-' + tag)
        attempt = base / 'attempt'
        fixture = base / 'fixture'
        output = base / 'saved'
        base.mkdir()
        log = ROOT / 'cases' / suffix / 'saved-only-command.log'
        run([sys.executable, str(REPO/'runtime.py'), 'materialize', '--manifest',
             str(MANIFEST), '--case', case, '--output', str(attempt)], base/'materialize.log')
        run([sys.executable, str(REPO/'runtime.py'), 'fixture', '--recipe',
             str(ROOT/'cases'/suffix/'fixture-recipe.json'), '--output', str(fixture)],
            base/'fixture.log')
        copy_sources(fixture, attempt)
        run([sys.executable, str(REPO/'runtime.py'), 'process-saved', '--manifest',
             str(MANIFEST), '--case', case, '--attempt', str(attempt), '--output',
             str(output), '--library', str(REPO/'runtime/library'), '--validator',
             str(VALIDATOR)], log)
        receipt = json.loads((output/'v0001/processing.json').read_text())
        if (receipt.get('passed') is not True or receipt.get('missing_evidence')
                or receipt.get('originals_preserved') is not True
                or receipt.get('physical_acceptance_claimed')
                or receipt.get('legal_acceptance_claimed')
                or not receipt.get('timestamp_joins', {}).get('passed')
                or receipt.get('final_video_checks', {}).get('passed') is not True):
            raise ValueError('Saved-only diagnostic proof incomplete: ' + suffix)
        compact = {'case_id': case, 'passed': True, 'recorded_only': True,
                   'diagnostic_fixture': True, 'manifest_sha256': selected,
                   'construction_sha256': receipt['analysis_revision']['construction_sha256'],
                   'originals_preserved': True, 'timestamp_frames': receipt['timestamp_joins']['frames'],
                   'final_video_frames': receipt['final_video_checks']['frames'],
                   'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
                   'command_log': str(log.relative_to(ROOT)), 'command_log_sha256': sha(log),
                   'scratch_processing_sha256': sha(output/'v0001/processing.json')}
        path = ROOT/'cases'/suffix/'saved-only-receipt.json'
        path.write_text(json.dumps(compact, sort_keys=True, indent=2)+'\n')
        summary['cases'].append({'case_id': case, 'receipt': str(path.relative_to(ROOT)),
                                 'sha256': sha(path)})
        print('saved-only passed', suffix, flush=True)
    (ROOT/'saved-only-summary.json').write_text(json.dumps(summary, sort_keys=True, indent=2)+'\n')


if __name__ == '__main__':
    main()
