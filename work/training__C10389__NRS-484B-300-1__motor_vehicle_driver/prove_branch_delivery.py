"""Positive diagnostic and negative Native acceptance audits for branch receipts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GRID = ('signal_red_stop', 'signal_red_proceed', 'signal_green_stop', 'signal_green_proceed',
        'officer_no_direction_stop', 'officer_no_direction_proceed',
        'officer_directed_stop', 'officer_directed_proceed')
PLACEMENT = ('placement_record_absent', 'placement_record_supplied')
CHECKS = ['native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_group(group, suffixes, scratch_name, version, manifest_name):
    scratch = ROOT / '.runtime-work' / scratch_name / '.runtime-work'
    manifest = HERE / manifest_name
    outputs = []
    for suffix in suffixes:
        dest = HERE / 'delivery-proof' / suffix
        dest.mkdir(parents=True, exist_ok=True)
        for candidate in ('primary', 'fallback1'):
            stem = suffix + '-' + candidate
            attempt = scratch / ('compat-' + version) / stem
            processing = scratch / ('saved-' + version) / stem / 'v0001/processing.json'
            if not processing.exists():
                raise ValueError('Saved branch proof missing: ' + stem)
            common = [str(ROOT / '.venv-cpu/bin/python'), str(HERE / 'branch_delivery_audit.py'),
                      '--manifest', str(manifest), '--case', HERE.name + '__' + suffix,
                      '--candidate', candidate, '--attempt', str(attempt),
                      '--processing', str(processing)]
            positive = dest / (candidate + '-diagnostic.json')
            positive_log = dest / (candidate + '-positive.log')
            command = [*common, '--output', str(positive), '--diagnostic']
            if positive.exists():
                positive.unlink()
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, env=os.environ.copy())
            positive_log.write_text(result.stdout.rstrip() + '\n')
            if result.returncode or json.loads(positive.read_text()).get('accepted') is not False:
                raise ValueError('Diagnostic delivery audit failed: ' + stem + ' ' + result.stdout[-500:])
            negative = dest / (candidate + '-negative-unused.json')
            negative_log = dest / (candidate + '-negative.log')
            negative_command = [*common, '--output', str(negative)]
            result = subprocess.run(negative_command, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, env=os.environ.copy())
            negative_log.write_text(result.stdout.rstrip() + '\n')
            if result.returncode == 0 or 'Original Native source required' not in result.stdout:
                raise ValueError('Synthetic Native acceptance was not rejected: ' + stem)
            outputs.append({'case_id': HERE.name + '__' + suffix, 'candidate_id': candidate,
                            'group': group, 'manifest_sha256': sha(manifest),
                            'positive_result': str(positive.relative_to(HERE)),
                            'positive_result_sha256': sha(positive),
                            'positive_command': ' '.join(command),
                            'positive_log': str(positive_log.relative_to(HERE)),
                            'positive_log_sha256': sha(positive_log), 'positive_exit_code': 0,
                            'negative_command': ' '.join(negative_command),
                            'negative_log': str(negative_log.relative_to(HERE)),
                            'negative_log_sha256': sha(negative_log),
                            'negative_exit_code': result.returncode,
                            'negative_expected_error': 'Original Native source required',
                            'accepted': False})
            print(stem, 'delivery diagnostic PASS', flush=True)
    path = HERE / 'delivery-proof' / (group + '-index.json')
    path.write_text(json.dumps({'format': 'c10389-branch-delivery-diagnostic-v1',
                                'group': group, 'entries': outputs, 'selected_delivery': False},
                               indent=2) + '\n')
    return outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--group', choices=('placement', 'grid'), required=True)
    args = parser.parse_args()
    if args.group == 'placement':
        run_group('placement', PLACEMENT, 'c10389-placement-compat-repo', 'v5',
                  'placement-draft-manifest.json')
    else:
        run_group('grid', GRID, 'c10389-branch-compat-repo', 'v3',
                  'branch-draft-manifest.json')


if __name__ == '__main__':
    main()
