"""Exercise root source-derived channels and removed-road rejection."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    scratch = ROOT / '.runtime-work/c110919-8c-owner104/root-channel-audit'
    if scratch.exists():
        raise ValueError('Root audit scratch already used')
    source = ROOT / '.runtime-work/c110919-8c-owner104/saved-probe_a-primary/attempt'
    config = HERE / 'config.json'
    if not source.is_dir() or not config.is_file():
        raise ValueError('Recorded source or root config missing')
    outcomes = []
    for condition in ('positive', 'missing_road'):
        attempt = scratch / condition / 'attempt'
        attempt.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, attempt, copy_function=os.link)
        shutil.copyfile(config, attempt / 'config.json')
        if condition == 'missing_road':
            (attempt / 'road_geometry.json').unlink()
        report = scratch / condition / 'analysis-report.json'
        completed = subprocess.run([sys.executable, str(HERE / 'finalize.py'), '--attempt', str(attempt),
                                    '--output', str(report)], text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=180,
                                   env={**os.environ, 'PYTHONPATH': str(ROOT / 'runtime/scenario_pipeline')})
        log = HERE / f'current-root-{condition}.log'
        log.write_text(completed.stdout)
        if condition == 'positive':
            if completed.returncode or not report.is_file():
                raise ValueError('Root derived-channel positive failed')
            names = {path.stem for path in (attempt / 'channels').glob('*.jsonl')}
            expected = {row['name'] for row in json.loads(config.read_text())['recording_description']['channels']}
            if names != expected or len(names) != 16:
                raise ValueError('Root source channel coverage differs')
            for name in names:
                if len((attempt / 'channels' / (name + '.jsonl')).read_text().splitlines()) != 600:
                    raise ValueError('Root derived channel has incomplete frame join: ' + name)
        elif completed.returncode == 0 or 'Missing required source: road_geometry.json' not in completed.stdout:
            raise ValueError('Root removed-road negative did not reject')
        outcomes.append({'condition': condition, 'exit_code': completed.returncode,
                         'log': log.relative_to(HERE).as_posix(), 'log_sha256': sha(log)})
    receipt = {'format': 'c110919-8c-root-channel-derivation', 'passed': True,
               'construction_sha256': sha(HERE / 'construction.json'),
               'source_sha256': {name: sha(source / name) for name in
                                 ('native_samples.jsonl', 'video_frames.jsonl', 'road_geometry.json')},
               'channels': 16, 'frames_per_channel': 600,
               'removed_road_negative': True, 'outcomes': outcomes,
               'original_native_observed': False}
    target = HERE / 'current-root-channel-proof.json'
    target.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': True, 'proof_sha256': sha(target), 'channels': 16}))


if __name__ == '__main__':
    run()
