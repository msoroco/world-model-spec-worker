"""Bind selected intersection CPU proofs into the exact delivery package."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def run(command, log):
    result = subprocess.run(command, capture_output=True, text=True)
    log.write_text((result.stdout + result.stderr).rstrip() + '\n')
    return result.returncode


def main():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    plan['summary_status'] = 'selected_delivery_cpu_prepared'
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary', 'coverage': [
            {'view': 'overview', 'subject': 'full vehicle, centerline and two-way intersection', 'interval': 'full 30 s'},
            {'view': 'approach', 'subject': '100-foot approach and intersection entry', 'interval': 'full 30 s'},
            {'view': 'reference_corner', 'subject': 'full vehicle footprint across intersection', 'interval': 'full 30 s'},
            {'view': 'driver_reference', 'subject': 'driver view of lane direction and crossing', 'interval': 'full 30 s'}]}
    plan['observations'] = [{'name': name, 'mandatory': True, 'reason': description}
                            for name, description in ((item['term'], item['note'])
                                                      for item in plan['source_observation_terms'])]
    plan['source_observation_mapping'] = {
        item['term']: {'evidence': 'Original 20 Hz Native body/map/camera source channel; physical highway and legal interpretation pending',
                       'channels': [item['term']],
                       'source_refs': [f'inputs/{HERE.name}/assignment.json']}
        for item in plan['source_observation_terms']}
    plan['evidence_review'] = {'method': 'Frozen accepted membership and witness review',
        'reviewer': 'worker source inventory', 'facts': [],
        'gaps': [{'id': 'intersection-approach-traversal',
                  'requirement': 'NRS 484B.213(2)(b) intersection approach and traversal',
                  'source': f'inputs/{HERE.name}/assignment.json',
                  'why_existing_insufficient': 'No accepted source-bound original recording membership supplied'}]}
    for case in plan['cases']:
        case.update(kind='delivery', selection_status='selected',
                    construction_status='cpu_prepared', gap_ids=['intersection-approach-traversal'])
    plan['requirement_dispositions'][0]['evidence_or_gap'] = (
        'Three selected source-bound current-v2 CPU packages and comparison; original physical roadway, pixels and legal outcome pending GPU delivery')
    write(plan_path, plan)

    manifest = json.loads((HERE / 'selected-probe-manifest.json').read_text())
    script = HERE / 'delivery-audit.py'
    expected_error = 'Original physical highway, body passage and four camera pixels required for delivery acceptance'
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        command = [sys.executable, str(script), '--case', case_id]
        positive = HERE / f'delivery-{suffix}-positive.log'
        negative = HERE / f'delivery-{suffix}-negative.log'
        if run(command + ['--diagnostic'], positive) != 0:
            raise ValueError('Diagnostic delivery audit failed: ' + suffix)
        negative_exit = run(command, negative)
        if negative_exit == 0 or expected_error not in negative.read_text():
            raise ValueError('Original acceptance negative failed: ' + suffix)
        entry['delivery_acceptance'] = {'case_id': case_id,
            'sets': ASSIGNMENT['selection_targets'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'script': script.name, 'script_sha256': sha(script),
            'command': f'.venv-cpu/bin/python work/{HERE.name}/delivery-audit.py --case {case_id} --diagnostic',
            'test_exit_code': 0, 'test_log': positive.name, 'test_log_sha256': sha(positive),
            'negative_command': f'.venv-cpu/bin/python work/{HERE.name}/delivery-audit.py --case {case_id}',
            'negative_exit_code': negative_exit, 'negative_expected_error': expected_error,
            'negative_log': negative.name, 'negative_log_sha256': sha(negative)}
    write(HERE / 'execution-manifest.json', manifest)

    construction = json.loads((HERE / 'selected-construction-probe_01.json').read_text())
    files = {item['path']: item['content'] for item in construction['files']}
    root_config = json.loads(files['config.json'])
    root_config['supported_case_ids'] = [item['case_id'] for item in manifest['cases']]
    files['config.json'] = json.dumps(root_config, indent=2, ensure_ascii=False) + '\n'
    construction['files'] = [{'path': name, 'content': content} for name, content in files.items()]
    for name, content in files.items():
        dest = HERE / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    write(HERE / 'construction.json', construction)

    comparison_script = HERE / 'comparison-audit.py'
    positive = HERE / 'comparison-positive.log'
    negative = HERE / 'comparison-negative.log'
    if run([sys.executable, str(comparison_script), '--diagnostic'], positive) != 0:
        raise ValueError('Selected comparison audit failed')
    negative_exit = run([sys.executable, str(comparison_script)], negative)
    expected = 'Original physical highway and paired Native body passage required for comparison acceptance'
    if negative_exit == 0 or expected not in negative.read_text():
        raise ValueError('Selected comparison negative failed')
    write(HERE / 'comparison-audit-proof.json', {
        'comparison_id': plan['comparisons'][0]['comparison_id'],
        'case_ids': [item['case_id'] for item in manifest['cases']],
        'script': comparison_script.name, 'script_sha256': sha(comparison_script),
        'positive_command': f'.venv-cpu/bin/python work/{HERE.name}/comparison-audit.py --diagnostic',
        'positive_exit_code': 0, 'positive_log': positive.name, 'positive_log_sha256': sha(positive),
        'negative_command': f'.venv-cpu/bin/python work/{HERE.name}/comparison-audit.py',
        'negative_exit_code': negative_exit, 'negative_log': negative.name,
        'negative_log_sha256': sha(negative), 'original_native_observed': False,
        'accepted_row_equivalence_claimed': False})
    print(json.dumps({'execution_manifest_sha256': sha(HERE / 'execution-manifest.json'),
                      'semantic_index_sha256': sha(HERE / 'proposals/semantic-index.json'),
                      'selected_case_ids': [item['case_id'] for item in manifest['cases']]}))


if __name__ == '__main__':
    main()
