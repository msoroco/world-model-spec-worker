"""Run exact 86/91.44/97 m compatibility, negative and saved CPU paths."""
import copy
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'signal-300-at-draft-manifest.json'
CASE = ROOT.name + '__signal_advance_300_at'
LIBRARY = 'runtime/library'
VALIDATOR = '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(command):
    process = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=360)
    require(process.returncode == 0,
            'Exact CPU processing failed: ' + ' '.join(command) + '\n'
            + process.stdout[-2000:] + process.stderr[-3000:])
    return json.loads(process.stdout)


def prove(tag, manifest_path):
    manifest = json.loads(manifest_path.read_text())
    require(len(manifest['cases']) in (1, 2), 'One or two exact draft cases required')
    evidence = []
    for entry in manifest['cases']:
      case = entry['case_id']
      target = entry['signal_target_m']
      require(case.startswith(ROOT.name + '__signal_advance_300_')
              and target in (86.0, 91.44, 97.0), 'Exact 300 ft draft identity required')
      label = 'at' if target == 91.44 else str(int(target))
      for ident in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        compat_dir = REPO / f'.runtime-work/c109749-signal-300-{label}-{ident}-compat-{tag}'
        saved_dir = REPO / f'.runtime-work/c109749-signal-300-{label}-{ident}-saved-{tag}'
        command = [str(REPO / '.venv-cpu/bin/python'), 'runtime.py', 'compatibility',
                   '--manifest', str(manifest_path.relative_to(REPO)), '--case', case,
                   '--output', str(compat_dir.relative_to(REPO)), '--library', LIBRARY,
                   '--validator', VALIDATOR]
        if ident != 'primary':
            command.extend(['--candidate', ident])
        receipt = run(command)
        construction = entry if ident == 'primary' else next(
            row for row in entry['candidates'] if row['id'] == ident)
        require(receipt['passed'] is True and receipt['case_id'] == case
                and receipt['candidate_id'] == ident
                and receipt['construction_sha256'] == construction['construction_sha256']
                and receipt['negative_removed'] == 'interaction_history.jsonl'
                and {'selected_measurements', 'negative_case_source',
                     'four_camera_sources', 'lean_decoder', 'final_decode'} <= set(receipt['checks'])
                and sha(compat_dir / 'negative-analysis.log') == receipt['negative_log_sha256']
                and b'Missing required source: interaction_history.jsonl'
                in (compat_dir / 'negative-analysis.log').read_bytes(),
                'Positive or missing-original negative compatibility differs')
        analysis = json.loads((compat_dir / 'analysis-report.json').read_text())
        observation = analysis['measurements']['signal_advance_observation']['value']
        distance = observation['observed_continuous_approach_distance_m']
        require(abs(distance - target) < .05
                and observation['probes']['91.44']['observable_distance_met'] is (target >= 91.44)
                and observation['probes']['91.44']['full_signal_onset_observed'] is True
                and observation['legal_verdict_asserted'] is False,
                'Saved-source 300 ft contrast observation differs')
        saved = run([str(REPO / '.venv-cpu/bin/python'), 'runtime.py', 'process-saved',
                     '--manifest', str(manifest_path.relative_to(REPO)), '--case', case,
                     '--attempt', str(compat_dir.relative_to(REPO)),
                     '--output', str(saved_dir.relative_to(REPO)),
                     '--library', LIBRARY, '--validator', VALIDATOR])
        processing = saved_dir / 'v0001/processing.json'
        require(saved['passed'] is True and saved['case_id'] == case
                and saved['recorded_only'] is True and saved['originals_preserved'] is True
                and saved['physical_acceptance_claimed'] is False
                and saved['legal_acceptance_claimed'] is False and processing.is_file(),
                'Recorded-only saved processing differs')
        evidence.append({'case_id': case, 'candidate_id': ident, 'observed_m': distance,
                         'construction_sha256': construction['construction_sha256'],
                         'compatibility_sha256': sha(compat_dir / 'compatibility.json'),
                         'negative_log_sha256': receipt['negative_log_sha256'],
                         'saved_processing_sha256': sha(processing)})
        print(json.dumps({'case_complete': case, 'candidate_complete': ident,
                          'observed_m': distance}), flush=True)
    require(len(evidence) == 4 * len(manifest['cases']), 'Every exact candidate path required')
    return {'format': 'worker-signal-300-processing-proof',
            'manifest_sha256': sha(manifest_path), 'paths': evidence,
            'source_kind': 'synthetic software diagnostic',
            'native_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', default='v2')
    parser.add_argument('--sides', action='store_true')
    args = parser.parse_args()
    require(args.tag.replace('_', '').replace('-', '').isalnum(), 'Simple isolated tag required')
    manifest_path = ROOT / ('signal-300-sides-draft-manifest.json' if args.sides
                            else 'signal-300-at-draft-manifest.json')
    entries = json.loads(manifest_path.read_text())['cases']
    # The runtime compatibility path requires a case-matched proposal. Restore
    # the canonical proposal bytes even when a diagnostic fails.
    proposal_path = ROOT / 'proposals/cases.json'
    plan_path = ROOT / 'case-plan.json'
    original = proposal_path.read_bytes()
    original_plan = plan_path.read_bytes()
    proposals = json.loads(original)
    plan = json.loads(original_plan)
    template = next(row for row in proposals['cases']
                    if row['case_id'].endswith('__signal_advance_100_at'))
    plan_template = next(item for item in plan['cases']
                         if item['case_id'].endswith('__signal_advance_100_at'))
    for entry in entries:
        case = entry['case_id']
        target = entry['signal_target_m']
        row = copy.deepcopy(template)
        row['case_id'] = case
        row['rationale'] = (f'Isolated {target:.2f} m signal-onset software diagnostic; '
                            'district and legal judgment unresolved.')
        row['paired_probe_id'] = 'c109749-signal-300-context-grid'
        row['deliberate_differences'] = ['authored onset distance and pre-yield approach speed']
        row['probe'] = {'primary_variable': 'continuous_left_signal_advance_m',
                        'comparison_or_standard': 'conditional 91.44 m observation reference',
                        'target_value_or_branch': target}
        proposals['cases'].append(row)
        planned = copy.deepcopy(plan_template)
        planned['case_id'] = case
        planned['objective'] = (f'Observe an authored {target:.2f} m continuous-signal '
                                'approach in an isolated diagnostic; district and '
                                'legal meaning unresolved.')
        plan['cases'].append(planned)
        for disposition in plan['requirement_dispositions']:
            if disposition['status'] == 'selected_required' and case not in disposition['case_ids']:
                disposition['case_ids'].append(case)
    try:
        proposal_path.write_text(json.dumps(proposals, indent=2) + '\n')
        plan_path.write_text(json.dumps(plan, indent=2) + '\n')
        print(json.dumps(prove(args.tag, manifest_path), indent=2))
    finally:
        proposal_path.write_bytes(original)
        plan_path.write_bytes(original_plan)


if __name__ == '__main__':
    main()
