"""Materialize the 30 s rider primary and fallbacks from 24 s drafts."""
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.name + '__rider_bicycle_clear'
SOURCE = HERE / 'draft-rider-cases/rider_bicycle_clear/primary/construction.json'
TARGET = HERE / 'rider-30s-primary/construction.json'
MANIFEST = HERE / 'rider-30s-primary/draft-manifest.json'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def replace_once(value, old, new):
    if value.count(old) != 1:
        raise ValueError('Unexpected construction text: ' + old)
    return value.replace(old, new)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def convert(source_path, target):
    source = json.loads(source_path.read_text())
    construction = json.loads(json.dumps(source))
    construction['status'] = 'unselected_30s_cpu_construction'
    construction['static_checks'] = [
        'exact bicycle clear case and original rider asset readback',
        '600 synchronized original Native frames at 20 Hz',
        'four original source camera views',
        'source-bound original rider and ego body samples',
    ]
    for channel in construction['recording_description']['channels']:
        channel['time_window'] = 'entire original 30 s / 600-frame attempt'
    construction['termination_rules'] = [
        '600 original frames', 'retain failure on capture or restoration error']
    for item in construction['files']:
        name = item['path']
        content = item['content']
        if name == 'config.json':
            config = json.loads(content)
            config['duration_s'] = 30
            for channel in config['recording_description']['channels']:
                channel['time_window'] = 'entire original 30 s / 600-frame attempt'
            content = json.dumps(config, indent=2) + '\n'
        elif name == 'runner.py':
            content = replace_once(content, "config['duration_s']!=24", "config['duration_s']!=30")
            content = content.replace('frames!=480', 'frames!=600')
            content = content.replace('frames==480', 'frames==600')
            content = replace_once(content, "'expected_frames':480", "'expected_frames':600")
            content = content.replace("\\\n+             (output/'native_samples.jsonl')", "\\\n             (output/'native_samples.jsonl')")
        elif name == 'finalize_rider.py':
            content = (HERE / 'native/finalize_rider.py').read_text()
            if content.count('!=480') != 3:
                raise ValueError('Unexpected rider finalizer frame checks')
            content = content.replace('!=480', '!=600')
            content = content.replace('verify_original_joins(attempt,480)',
                                      'verify_original_joins(attempt,600)')
            content = content.replace('len(rider_rows)!=480', 'len(rider_rows)!=600')
            content = content.replace('count!=480', 'count!=600')
            content = content.replace('480-frame', '600-frame')
            content = content.replace('entire 24 s', 'entire 30 s')
            content = content.replace("[0,24]", "[0,30]")
        elif name == 'measure_rider_yield.py':
            content = (HERE / 'native/measure_rider_yield.py').read_text()
            content = content.replace('len(rows) != 480', 'len(rows) != 600')
            content = content.replace('480 original frames', '600 original frames')
        elif name == 'measure_rider_native.py':
            content = (HERE / 'native/measure_rider_native.py').read_text()
        if name.endswith('.py'):
            ast.parse(content, filename=name)
        item['content'] = content
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(construction, indent=2) + '\n')
    return sha(target)


def main():
    digests = {}
    for candidate in CANDIDATES:
        source = HERE / 'draft-rider-cases/rider_bicycle_clear' / candidate / 'construction.json'
        target = TARGET if candidate == 'primary' else \
            TARGET.parent / candidate / 'construction.json'
        digests[candidate] = convert(source, target)
    base_manifest = json.loads((HERE / 'draft-rider-execution-manifest.json').read_text())
    entry = next(row for row in base_manifest['cases'] if row['case_id'] == CASE)
    entry['construction'] = TARGET.name
    entry['construction_sha256'] = digests['primary']
    for candidate in entry['candidates']:
        name = candidate['id']
        candidate['construction'] = name + '/construction.json'
        candidate['construction_sha256'] = digests[name]
    base_manifest['cases'] = [entry]
    base_manifest['status'] = 'draft_not_selected'
    MANIFEST.write_text(json.dumps(base_manifest, indent=2) + '\n')
    print(json.dumps({'construction_sha256': digests,
                      'manifest_sha256': sha(MANIFEST),
                      'expected_frames': 600, 'duration_s': 30,
                      'selected': False}))


if __name__ == '__main__':
    main()
