"""Run exact offline checks for the two staged signal-distance probe bundles."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
INDEX = ROOT / 'signal-distance-draft-index.json'
MANIFEST = ROOT / 'signal-distance-draft-manifest.json'
sys.path.insert(0, str(ROOT))
from signal_advance_audit import measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    index = json.loads(INDEX.read_text())
    manifest = json.loads(MANIFEST.read_text())
    require(len(index['cases']) == len(manifest['cases']) == 2,
            'Two staged signal-distance cases required')
    evidence = []
    for row, runtime_case in zip(index['cases'], manifest['cases']):
        distance = row['signal_target_m']
        steps = int(distance / .25)
        history = [{'frame': index, 'time_s': (index + 1) / 20,
                    'ego': {'position_xy_m': [index * .25, 0.]},
                    'ego_heading_deg': 20. if index == steps + 2 else 0.,
                    'ego_left_indicator': index >= 1}
                   for index in range(steps + 3)]
        measurement = measure(history, probes_m=(30.48,))
        require(abs(measurement['observed_continuous_approach_distance_m'] - distance) < 1e-9
                and measurement['probes']['30.48']['observable_distance_met'] == (distance >= 30.48)
                and measurement['probes']['30.48']['full_signal_onset_observed'] is True
                and measurement['legal_verdict_asserted'] is False,
                'Observed signal-distance boundary behavior differs')
        require(row['case_id'] == runtime_case['case_id']
                and row['signal_target_m'] == runtime_case['signal_target_m']
                and len(row['variants']) == 4,
                'Signal-distance case identity or variants differ')
        for variant in row['variants']:
            path = ROOT / variant['construction']
            require(sha(path) == variant['construction_sha256'],
                    'Signal-distance construction changed')
            construction = json.loads(path.read_text())
            files = {item['path']: item['content'] for item in construction['files']}
            config = json.loads(files['config.json'])
            require(construction['case_id'] == row['case_id']
                    and config['selected_case_id'] == row['case_id']
                    and config['signal_target_m'] == row['signal_target_m']
                    and f"config.get('signal_target_m') != {row['signal_target_m']:.1f}" in files['runner.py']
                    and config['rate_hz'] == 20 and config['duration_s'] == 45
                    and len(config['cameras']) == 4,
                    'Signal-distance Native bundle differs')
            target_line = "{'target':'continuous_left_signal_at_least_30_48_m',\n                        'requested':"
            require(target_line + ('True,' if distance >= 30.48 else 'False,')
                    in files['finalizer.py'], 'Saved target expectation differs')
            if distance < 30.48:
                require("'matched':not (signal_advance['probes']['30.48']" in files['finalizer.py'],
                        'Saved shortfall must be preserved as a negative observation')
            label = 'below' if row['signal_target_m'] == 25.0 else 'above'
            output = f'.runtime-work/c109749-signal-distance-{label}-{variant["id"]}-offline-v5'
            command = [str(REPO / '.venv-cpu/bin/python'), 'runtime.py', 'offline',
                       '--manifest', str(MANIFEST.relative_to(REPO)),
                       '--case', row['case_id'], '--output', output]
            if variant['id'] != 'primary':
                command.extend(['--candidate', variant['id']])
            process = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
            require(process.returncode == 0,
                    'Exact offline failed: ' + ' '.join(command) + '\n' + process.stderr)
            receipt = json.loads(process.stdout)
            log = Path(receipt['log'])
            require(receipt['case_id'] == row['case_id']
                    and receipt['candidate_id'] == variant['id']
                    and receipt['offline_passed'] is True
                    and receipt['simulation_started'] is False
                    and log.is_file() and 'OK' in log.read_text(),
                    'Exact offline receipt or CPU tests differ')
            evidence.append({'case_id': row['case_id'], 'candidate_id': variant['id'],
                             'signal_target_m': row['signal_target_m'],
                             'construction_sha256': sha(path),
                             'command': ' '.join(command),
                             'offline_log_sha256': sha(log)})
    require(len(evidence) == 8, 'Eight exact offline checks required')
    print(json.dumps({'format': 'c109749-signal-distance-draft-offline-proof',
                      'manifest_sha256': sha(MANIFEST), 'variants': evidence,
                      'source_kind': 'CPU construction and offline tests',
                      'compatibility_or_physical_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
