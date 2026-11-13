"""Run positive/negative compatibility and saved processing for staged probes."""

import hashlib
import json
import copy
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'signal-distance-draft-manifest.json'
LIBRARY = 'runtime/library'
VALIDATOR = '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(command):
    process = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=300)
    require(process.returncode == 0,
            'CPU processing failed: ' + ' '.join(command) + '\n' + process.stderr[-3000:])
    return json.loads(process.stdout)


def run_proofs():
    manifest = json.loads(MANIFEST.read_text())
    proofs = []
    for entry in manifest['cases']:
        case = entry['case_id']
        distance = entry['signal_target_m']
        label = 'below' if distance == 25.0 else 'above'
        for ident in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            suffix = f'c109749-signal-distance-{label}-{ident}'
            compat_dir = REPO / f'.runtime-work/{suffix}-compat-v5'
            saved_dir = REPO / f'.runtime-work/{suffix}-saved-v5'
            command = [str(REPO / '.venv-cpu/bin/python'), 'runtime.py', 'compatibility',
                       '--manifest', str(MANIFEST.relative_to(REPO)), '--case', case,
                       '--output', str(compat_dir.relative_to(REPO)),
                       '--library', LIBRARY, '--validator', VALIDATOR]
            if ident != 'primary':
                command.extend(['--candidate', ident])
            receipt = run(command)
            construction = (entry if ident == 'primary' else
                            next(row for row in entry['candidates'] if row['id'] == ident))
            require(receipt['passed'] is True and receipt['case_id'] == case
                    and receipt['candidate_id'] == ident
                    and receipt['construction_sha256'] == construction['construction_sha256']
                    and receipt['negative_removed'] == 'interaction_history.jsonl'
                    and {'selected_measurements', 'negative_case_source',
                         'four_camera_sources', 'lean_decoder', 'final_decode'} <= set(receipt['checks'])
                    and sha(compat_dir / 'negative-analysis.log') == receipt['negative_log_sha256']
                    and b'Missing required source: interaction_history.jsonl'
                    in (compat_dir / 'negative-analysis.log').read_bytes(),
                    'Exact compatibility or missing-source rejection differs')
            analysis = json.loads((compat_dir / 'analysis-report.json').read_text())
            probe = analysis['measurements']['signal_advance_observation']['value']
            observed = probe['observed_continuous_approach_distance_m']
            require(abs(observed - distance) < .05
                    and probe['probes']['30.48']['observable_distance_met'] == (distance >= 30.48)
                    and probe['probes']['30.48']['full_signal_onset_observed'] is True
                    and probe['legal_verdict_asserted'] is False,
                    'Source-measured signal distance differs')
            saved = run([str(REPO / '.venv-cpu/bin/python'), 'runtime.py', 'process-saved',
                         '--manifest', str(MANIFEST.relative_to(REPO)), '--case', case,
                         '--attempt', str(compat_dir.relative_to(REPO)),
                         '--output', str(saved_dir.relative_to(REPO)),
                         '--library', LIBRARY, '--validator', VALIDATOR])
            processing = saved_dir / 'v0001/processing.json'
            require(saved['passed'] is True and saved['case_id'] == case
                    and saved['recorded_only'] is True and saved['originals_preserved'] is True
                    and saved['physical_acceptance_claimed'] is False
                    and saved['legal_acceptance_claimed'] is False
                    and processing.is_file(), 'Recorded-only processing differs')
            proofs.append({'case_id': case, 'candidate_id': ident,
                           'authored_target_m': distance, 'measured_fixture_m': observed,
                           'compatibility_sha256': sha(compat_dir / 'compatibility.json'),
                           'negative_log_sha256': receipt['negative_log_sha256'],
                           'saved_processing_sha256': sha(processing),
                           'construction_sha256': construction['construction_sha256']})
        print(json.dumps({'case_complete': case, 'candidate_count': 4}), flush=True)
    require(len(proofs) == 8, 'Eight exact processing paths required')
    print(json.dumps({'format': 'c109749-signal-distance-processing-proof',
                      'manifest_sha256': sha(MANIFEST), 'proofs': proofs,
                      'source_kind': 'synthetic software diagnostics',
                      'native_or_legal_acceptance_claimed': False}, indent=2))


def main():
    # Compatibility needs a matching proposal for each isolated diagnostic.
    # Keep canonical proposals byte-for-byte identical outside this proof run.
    proposal_path = ROOT / 'proposals/cases.json'
    original = proposal_path.read_bytes()
    proposals = json.loads(original)
    template = next(row for row in proposals['cases']
                    if row['case_id'].endswith('__signal_advance_100_at'))
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        row = copy.deepcopy(template)
        row['case_id'] = entry['case_id']
        row['rationale'] = 'Staged source-measured signal-onset diagnostic; no legal verdict.'
        row['paired_probe_id'] = 'c109749-signal-distance-25-30_48-36'
        row['deliberate_differences'] = ['authored signal onset distance']
        row['probe'] = {'primary_variable': 'left_signal_enabled',
                        'comparison_or_standard': 'observed 30.48 m reference',
                        'target_value_or_branch': entry['signal_target_m']}
        proposals['cases'].append(row)
    try:
        proposal_path.write_text(json.dumps(proposals, indent=2) + '\n')
        run_proofs()
    finally:
        proposal_path.write_bytes(original)


if __name__ == '__main__':
    main()
