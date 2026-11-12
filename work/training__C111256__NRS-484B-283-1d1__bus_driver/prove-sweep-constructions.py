"""Exercise every exact sweep construction without CARLA or original acceptance."""
import hashlib
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'


def read(path):
    return json.loads(path.read_text())


def materialize(construction, folder):
    folder.mkdir()
    for item in construction['files']:
        target = folder / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])


def run(folder, *args):
    completed = subprocess.run([str(PYTHON), *args], cwd=folder,
                               text=True, capture_output=True, timeout=120)
    if completed.returncode:
        raise ValueError(f"CPU construction failed in {folder.name}: {completed.stderr[-1400:]}")
    return completed.stdout


def main(tag):
    stage_path = HERE / 'proposals/sweep-stage-candidate.json'
    manifest = read(HERE / 'sweep-execution-candidate.json')
    if manifest['case_stage_sha256'] != hashlib.sha256(stage_path.read_bytes()).hexdigest():
        raise ValueError('Sweep candidate manifest lost stage binding')
    if len(manifest['cases']) != 4:
        raise ValueError('Incomplete four-point sweep')
    proven = []
    with tempfile.TemporaryDirectory(prefix='c111256-sweep-', dir=REPO / '.runtime-work') as scratch:
        for case in manifest['cases']:
            setpoint = case['setpoint_margin_m']
            candidates = [{'id': 'primary', 'construction': case['construction'],
                           'construction_sha256': case['construction_sha256']},
                          *case['candidates']]
            if len(candidates) != 4 or len({c['id'] for c in candidates}) != 4:
                raise ValueError('Sweep case lacks primary and three fallbacks')
            if len({(c['trigger']['source'], c['trigger']['metric']) for c in case['candidates']}) != 3:
                raise ValueError('Sweep fallback physical triggers overlap')
            for candidate in candidates:
                path = HERE / candidate['construction']
                if hashlib.sha256(path.read_bytes()).hexdigest() != candidate['construction_sha256']:
                    raise ValueError('Sweep candidate construction hash changed')
                construction = read(path)
                folder = Path(scratch) / (case['case_id'].rsplit('__', 1)[-1] + '-' + candidate['id'])
                materialize(construction, folder)
                config = read(folder / 'config.json')
                if (config['case_id'] != case['case_id'] or
                        config['knobs']['crosswalk_hold_margin_m'] != setpoint):
                    raise ValueError('Fallback changed frozen sweep setpoint')
                result = json.loads(run(folder, 'runner.py', '--check'))
                if result['carla_imported'] or result['physical_walk_observed']:
                    raise ValueError('Offline proof claimed physical observation')
                run(folder, '-m', 'unittest', 'discover', '-s', 'tests')
                # The runner must reject an altered exact setpoint or case identity.
                original = (folder / 'config.json').read_text()
                config['knobs']['crosswalk_hold_margin_m'] += .25
                (folder / 'config.json').write_text(json.dumps(config))
                bad = subprocess.run([str(PYTHON), 'runner.py', '--check'], cwd=folder,
                                     text=True, capture_output=True, timeout=120)
                if bad.returncode == 0 or 'candidate knobs differ' not in bad.stderr:
                    raise ValueError('Altered frozen sweep margin was accepted')
                (folder / 'config.json').write_text(original)
                proven.append({'case_id': case['case_id'], 'candidate': candidate['id'],
                               'construction_sha256': candidate['construction_sha256'],
                               'setpoint_margin_m': setpoint,
                               'runner_check': 'passed', 'bundled_tests': 'passed',
                               'setpoint_mutation_rejected': True})
    result = {'format': 'c111256-unselected-sweep-construction-proof-v1',
              'candidate_manifest_sha256': hashlib.sha256(
                  (HERE / 'sweep-execution-candidate.json').read_bytes()).hexdigest(),
              'stage_sha256': manifest['case_stage_sha256'],
              'bundles': proven, 'offline_bundles_passed': len(proven),
              'setpoint_mutations_rejected': len(proven),
              'selected': False, 'original_recordings_accepted': 0}
    path = HERE / f'{tag}-sweep-construction-proof.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'proof': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'offline_bundles_passed': len(proven),
                      'setpoint_mutations_rejected': len(proven),
                      'selected': False}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', default='update029')
    main(parser.parse_args().tag)
