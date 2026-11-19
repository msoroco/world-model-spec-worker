"""Audit source isolation for the pedestrian signal and clearance comparisons."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREFIX = 'heldout__C111610__NRS-484B-413-1__motor_vehicle_driver__'
IDS = {'horn': PREFIX + 'pedestrian_horn_before_turn',
       'no_horn': PREFIX + 'pedestrian_no_horn_before_turn',
       'far': PREFIX + 'pedestrian_farther_horn_before_turn'}
FAR = IDS['far']


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    receipts = {entry['case_id']: json.loads((ROOT / entry['compatibility']['receipt']).read_text())
                for entry in manifest['cases']}
    return manifest, receipts


def _entries(manifest, receipts, names):
    entries = {entry['case_id']: entry for entry in manifest['cases']}
    for name in names:
        require(name in entries and name in receipts, 'Missing selected comparison case')
        entry, receipt = entries[name], receipts[name]
        path = ROOT / entry['compatibility']['receipt']
        require(_sha(path) == entry['compatibility']['sha256'], 'Stale compatibility receipt file')
        require(receipt['construction_sha256'] == entry['construction_sha256'] and
                _sha(ROOT / entry['construction']) == entry['construction_sha256'],
                'Stale construction binding')
        require(receipt['passed'] is True and receipt['case_id'] == name,
                'Unproved exact comparison case')
    return entries


def _value(receipts, name):
    return receipts[name]['measurement_examples']['turn_signal_observation']['value']


def inspect(manifest, receipts):
    _entries(manifest, receipts, (IDS['horn'], IDS['no_horn']))
    horn, quiet = (_value(receipts, IDS[name]) for name in ('horn', 'no_horn'))
    require(horn['sources']['ego_turn_motion.jsonl'] == quiet['sources']['ego_turn_motion.jsonl'],
            'Fixed original turn changed')
    require(horn['sources']['participant_bodies.jsonl'] == quiet['sources']['participant_bodies.jsonl'],
            'Pedestrian body path changed')
    require(horn['max_pre_turn_listener_audio_rms'] is not None and
            quiet['max_pre_turn_listener_audio_rms'] is not None and
            horn['max_pre_turn_listener_audio_rms'] > quiet['max_pre_turn_listener_audio_rms'] + .1,
            'Horn contrast absent')
    return {'passed': True, 'comparison': 'pedestrian_horn_timing',
            'pre_turn_listener_audio_rms': [horn['max_pre_turn_listener_audio_rms'],
                                            quiet['max_pre_turn_listener_audio_rms']],
            'legal_audibility_decided': False}


def inspect_clearance(manifest, receipts):
    _entries(manifest, receipts, (IDS['horn'], FAR))
    near, far = _value(receipts, IDS['horn']), _value(receipts, FAR)
    require(near['sources']['ego_turn_motion.jsonl'] == far['sources']['ego_turn_motion.jsonl'],
            'fixed original changed')
    require(near['sources']['participant_bodies.jsonl'] != far['sources']['participant_bodies.jsonl'],
            'body source unchanged')
    gaps = [near['participant_clearance']['ped_listener']['minimum_sampled_surface_gap_m'],
            far['participant_clearance']['ped_listener']['minimum_sampled_surface_gap_m']]
    require(all(isinstance(g, (int, float)) for g in gaps) and gaps[0] < gaps[1],
            'Pedestrian clearance contrast absent')
    return {'passed': True, 'comparison': 'pedestrian_clearance_sweep',
            'minimum_sampled_surface_gap_m': gaps, 'legal_safety_decided': False}


def main():
    if sys.argv[1:] == ['--self-test']:
        for directory in (ROOT / 'tests', ROOT / 'native_horn' / 'tests'):
            run = subprocess.run([sys.executable, '-m', 'unittest', 'discover',
                                  '-s', str(directory), '-v'], text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            print(run.stdout, end='')
            require(run.returncode == 0, 'C111610 unit tests failed: ' + str(directory))
    else:
        require(not sys.argv[1:], 'Unknown comparison audit option')
    manifest, receipts = load()
    print(json.dumps({'horn': inspect(manifest, receipts),
                      'clearance': inspect_clearance(manifest, receipts)}, indent=2))


if __name__ == '__main__':
    main()
