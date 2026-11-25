"""Prove selected hand-signal delivery audit and original-source rejection."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from hand_signal_delivery_audit import selected_statutory_context, driver_signal_frames

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__preparing_hand_signal'
CHECKS = ['native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(line.rstrip() for line in text.splitlines()).rstrip() + '\n')


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'] == CASE)
    script = HERE / 'hand_signal_delivery_audit.py'
    sources = ('ego_driver_source', 'ego_vehicle_source',
               'emergency_authorization_source', 'qualifying_flash_equipment_source',
               'flashing_light_visual_source', 'lane_boundary_source',
               'officer_direction_review_source')
    signal_sources = ('driver_hand_signal_visual_source',
                      'driver_signal_actor_identity_source', 'driver_signal_window_source',
                      'driver_signal_visual_review_source', 'driver_signal_reviewer')
    context = {'case_id': CASE, 'review_kind': 'original_source_review',
               'reviewer': 'source-shaped independent reviewer',
               'emergency_vehicle_authorized': True,
               'qualifying_flash_equipment_reviewed': True,
               'officer_directed_otherwise': False,
               'preparing_to_move_reviewed': True, 'driver_signal_actor_id': 3,
               **{key: 'source-shaped:' + key for key in signal_sources},
               **{key: 'source-shaped:' + key for key in sources}}
    selected_statutory_context(context, CASE)
    for key in signal_sources:
        changed = json.loads(json.dumps(context))
        changed[key] = ''
        try:
            selected_statutory_context(changed, CASE)
        except ValueError:
            pass
        else:
            raise ValueError('Missing driver hand-signal source accepted: ' + key)
    changed = dict(context, driver_signal_actor_id=None)
    try:
        selected_statutory_context(changed, CASE)
    except ValueError:
        pass
    else:
        raise ValueError('Absent driver signal actor accepted')
    attempt = ROOT / '.runtime-work/c404492-hand-public-primary-v2'
    processing = HERE / 'current-hand-signal-saved/primary.json'
    scratch = ROOT / '.runtime-work/c404492-hand-audit'
    scratch.mkdir(parents=True, exist_ok=True)
    output = scratch / 'diagnostic.json'
    output.unlink(missing_ok=True)
    base = [sys.executable, str(script), '--case', CASE, '--candidate', 'primary',
            '--attempt', str(attempt), '--processing', str(processing),
            '--output', str(output)]
    env = dict(os.environ, TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch))
    positive = subprocess.run(base + ['--diagnostic'], cwd=ROOT, env=env,
                              text=True, capture_output=True)
    if positive.returncode:
        raise ValueError(positive.stdout + positive.stderr)
    value = json.loads(output.read_text())
    if value['accepted'] or not value['diagnostic_only']:
        raise ValueError('Diagnostic hand-signal audit claimed acceptance')
    folder = HERE / 'delivery-proofs/preparing_hand_signal'
    positive_log = folder / 'diagnostic.log'
    write(positive_log, positive.stdout + positive.stderr)
    output.unlink()
    negative = subprocess.run(base, cwd=ROOT, env=env, text=True, capture_output=True)
    expected = 'Original Native source required'
    if negative.returncode == 0 or expected not in negative.stderr:
        raise ValueError('Original Native negative absent: ' + negative.stderr)
    negative_log = folder / 'native-required.log'
    write(negative_log, negative.stdout + negative.stderr)
    altered = scratch / 'tampered-processing.json'
    changed = json.loads(processing.read_text())
    changed['original_source_hashes']['vehicle_poses.jsonl'] = '0' * 64
    altered.write_text(json.dumps(changed) + '\n')
    tamper_command = list(base)
    tamper_command[tamper_command.index(str(processing))] = str(altered)
    tamper = subprocess.run(tamper_command + ['--diagnostic'], cwd=ROOT, env=env,
                            text=True, capture_output=True)
    if tamper.returncode == 0 or 'Saved original source changed: vehicle_poses.jsonl' not in tamper.stderr:
        raise ValueError('Changed original source escaped audit')
    write(folder / 'source-hash-required.log', tamper.stdout + tamper.stderr)
    altered.unlink()
    entry['delivery_acceptance'] = {
        'case_id': CASE, 'sets': ['full-train'], 'checks': CHECKS,
        'command': ' '.join(base + ['--diagnostic']),
        'negative_command': ' '.join(base),
        'script': script.name, 'script_sha256': sha(script),
        'test_exit_code': 0, 'negative_exit_code': negative.returncode,
        'negative_expected_error': expected,
        'test_log': positive_log.relative_to(HERE).as_posix(),
        'test_log_sha256': sha(positive_log),
        'negative_log': negative_log.relative_to(HERE).as_posix(),
        'negative_log_sha256': sha(negative_log),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'delivery_script_sha256': sha(script),
                      'manifest_sha256': sha(manifest_path),
                      'diagnostic_accepted': False,
                      'signal_source_negatives': len(signal_sources)}))


if __name__ == '__main__':
    main()
