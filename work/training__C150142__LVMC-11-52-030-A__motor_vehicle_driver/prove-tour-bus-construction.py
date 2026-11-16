"""Exercise the exact long-runner static path without importing CARLA."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__tour_bus_below'


def materialize(target, package):
    for row in package['files']:
        path = target / row['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(row['content'])


def run(target, *args):
    return subprocess.run([sys.executable, *map(str, args)], cwd=target,
                          text=True, capture_output=True)


def prove():
    package = json.loads((ROOT / 'selected-primary/tour_bus_below/construction.json').read_text())
    if package['case_id'] != CASE:
        raise ValueError('Exact tour-bus construction missing')
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='C150142-tour-bus-') as tmp:
        target = Path(tmp)
        materialize(target, package)
        positive = run(target, 'runner.py', '--check')
        if positive.returncode:
            raise AssertionError('Tour-bus static check failed: ' + positive.stderr[-2000:])
        checked = json.loads(positive.stdout)
        if checked['frames'] != 36120 or checked['original_native_observed']:
            raise AssertionError('Long capture check differs')
        unit = run(target, '-m', 'unittest', 'discover', '-s', 'tests')
        if unit.returncode:
            raise AssertionError('Tour-bus bundled tests failed: ' + unit.stderr[-2000:])
        cfg_path = target / 'config.json'
        original = cfg_path.read_text()
        for change, pattern in (
                ({'capture_frames': 240}, 'capture contract'),
                ({'native_blueprint': 'vehicle.tesla.model3'}, 'Tour-bus vehicle'),
                ({'sign_classes': ['no_parking']}, 'Signed curb construction')):
            cfg = json.loads(original)
            cfg.update(change)
            cfg_path.write_text(json.dumps(cfg) + '\n')
            rejected = run(target, 'runner.py', '--check')
            if rejected.returncode == 0 or pattern not in rejected.stderr:
                raise AssertionError('Changed tour-bus source was accepted: ' + str(change))
        cfg_path.write_text(original)
    return {'case_id': CASE, 'capture_frames': 36120,
            'bundled_tests': 'passed', 'negative_rejections': 3,
            'carla_executed': False}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
