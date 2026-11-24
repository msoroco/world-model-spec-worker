"""Build 30-second revisions of the two unselected curb probes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Expected one duration token: ' + old)
    return source.replace(old, new)


def revise(construction):
    construction = json.loads(json.dumps(construction))
    for row in construction['files']:
        source = row['content']
        if row['path'] == 'runner.py':
            source = replace_once(source, 'FRAMES = 240', 'FRAMES = 600')
            source = replace_once(source, "!= (12, RATE_HZ)", "!= (30, RATE_HZ)")
        elif row['path'] == 'curb.py':
            source = replace_once(source, 'len(rows) != 240', 'len(rows) != 600')
            source = replace_once(source, 'Full 240-frame curb source required', 'Full 600-frame curb source required')
        elif row['path'] == 'finalize.py':
            source = replace_once(source, 'count != 240', 'count != 600')
            source = replace_once(source, 'Full 12-second curb window changed', 'Full 30-second curb window changed')
        elif row['path'] == 'tests/test_offline.py':
            source = replace_once(source, "result['frames'], 240", "result['frames'], 600")
        elif row['path'] == 'config.json':
            config = json.loads(source)
            if config['duration_s'] != 12 or config['rate_hz'] != 20:
                raise ValueError('Unexpected source duration')
            config['duration_s'] = 30
            for channel in config['recording_description']['channels']:
                channel['time_window'] = 'entire 600-frame 30-second approach'
            source = json.dumps(config, indent=2) + '\n'
        row['content'] = source
    for channel in construction['recording_description']['channels']:
        channel['time_window'] = 'entire 600-frame 30-second approach'
    construction['termination_rules'] = [
        '600 original frames at 20 Hz',
        'retain failure, encoder and world restoration evidence',
    ]
    construction['measurement_plan']['status'] = 'unselected_600_frame_cpu_prototype'
    construction['status'] = 'unselected_30_second_cpu_draft_physical_yield_unverified'
    return construction


def main():
    old = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    manifest = {
        'format': 'worker-unselected-draft-construction-manifest-v1',
        'assignment_id': HERE.name,
        'runtime_manifest_sha256': json.loads((ROOT / 'batch.json').read_text())['runtime']['source_manifest_sha256'],
        'status': 'draft_not_selected', 'cases': [],
    }
    for entry in old['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        source = HERE / 'draft-bundles' / suffix / 'primary' / 'construction.json'
        construction = revise(json.loads(source.read_text()))
        target = HERE / 'duration-probes' / suffix / 'construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(construction, indent=2) + '\n')
        manifest['cases'].append({
            'case_id': entry['case_id'], 'kind': 'draft_not_selected',
            'id': 'primary', 'construction': str(target.relative_to(HERE / 'duration-probes')),
            'construction_sha256': sha(target), 'candidates': [],
            'candidate_risk': entry['candidate_risk'],
            'measurement_contract': entry['measurement_contract'],
            'measurement_procedure': entry['measurement_procedure'],
        })
    output = HERE / 'duration-probes' / 'manifest.json'
    output.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'frames': 600,
                      'manifest_sha256': sha(output)}))


if __name__ == '__main__':
    main()
