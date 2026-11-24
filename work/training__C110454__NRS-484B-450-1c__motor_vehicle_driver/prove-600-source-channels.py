"""Prove exact 600-frame drafts derive channels from retained source rows."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'draft-execution-manifest-600.json'
sys.path.insert(0, str(HERE))
from synthetic_proof import sample  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path, values):
    path.write_text(''.join(json.dumps(item, allow_nan=False) + '\n' for item in values))


def main():
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c110454-source-channels')
    manifest = json.loads(MANIFEST.read_text())
    finalizer_hashes = {}
    for entry in manifest['cases']:
        for reference in [entry] + entry['candidates']:
            construction = HERE / reference['construction']
            assert sha(construction) == reference['construction_sha256']
            bundle = json.loads(construction.read_text())
            finalizer = next(item['content'] for item in bundle['files']
                             if item['path'] == 'finalize.py')
            assert 'def derive_channels(' in finalizer
            finalizer_hashes[entry['case_id'] + '/' + reference['id']] = \
                hashlib.sha256(finalizer.encode()).hexdigest()
    assert len(finalizer_hashes) == 8 and len(set(finalizer_hashes.values())) == 1
    checks = []
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c110454-source-channels-') as temp:
        scratch = Path(temp)
        for suffix in ('probe_a', 'probe_b'):
            case_id = HERE.name + '__' + suffix
            attempt = scratch / suffix
            command = [sys.executable, str(ROOT / 'runtime.py'), 'materialize',
                       '--manifest', str(MANIFEST), '--case', case_id,
                       '--candidate', 'primary', '--output', str(attempt)]
            completed = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       timeout=180)
            if completed.returncode:
                raise AssertionError(completed.stdout)
            motion = [sample(suffix, i) for i in range(600)]
            mapping = [{'video_frame': i, 'native_frame': row['native_frame'],
                        'carla_frame': row['native_frame'], 'time_s': row['time_s']}
                       for i, row in enumerate(motion)]
            survey = {'intersection_polygon_xy_m': [[-7,-7],[7,-7],[7,7],[-7,7]],
                      'native_signal_count': 0, 'source_kind': 'synthetic_cpu_fixture'}
            write_rows(attempt / 'native_samples.jsonl', motion)
            write_rows(attempt / 'video_frames.jsonl', mapping)
            (attempt / 'road_geometry.json').write_text(json.dumps(survey) + '\n')
            source_hashes = {name: sha(attempt / name) for name in
                             ('native_samples.jsonl','video_frames.jsonl','road_geometry.json')}
            sys.path.insert(0, str(attempt))
            try:
                derive = runpy.run_path(str(attempt / 'finalize.py'))['derive_channels']
            finally:
                sys.path.pop(0)
            description = json.loads((attempt / 'config.json').read_text())['recording_description']
            result = derive(attempt, description)
            assert result['rows_per_channel'] == 600
            assert result['channels'] == len(description['channels']) == 9
            assert result['source_sha256'] == source_hashes
            assert all(sha(attempt / name) == digest for name,digest in source_hashes.items())
            channels = attempt / 'channels'
            assert len(list(channels.glob('*.jsonl'))) == 9
            assert all(len(path.read_text().splitlines()) == 600 for path in channels.glob('*.jsonl'))
            occupancy = [json.loads(line)['value'] for line in
                         (channels / 'rel.occupies.jsonl').read_text().splitlines()]
            assert all(value['body_xy_m'] == motion[i]['body_xy_m'] for i,value in enumerate(occupancy))
            bad = scratch / (suffix + '-badjoin')
            bad.mkdir()
            (bad / 'native_samples.jsonl').write_bytes((attempt / 'native_samples.jsonl').read_bytes())
            (bad / 'road_geometry.json').write_bytes((attempt / 'road_geometry.json').read_bytes())
            changed = list(mapping)
            changed[42] = dict(changed[42], native_frame=changed[42]['native_frame'] + 1)
            write_rows(bad / 'video_frames.jsonl', changed)
            try:
                derive(bad, description)
            except ValueError as error:
                assert 'frame/time join differs' in str(error)
            else:
                raise AssertionError('Changed Native frame mapping accepted')
            try:
                derive(attempt, description)
            except ValueError as error:
                assert 'Preexisting derived channels' in str(error)
            else:
                raise AssertionError('Preexisting derived channels accepted')
            checks.append({'case_id':case_id,'construction_sha256':
                           next(entry['construction_sha256'] for entry in manifest['cases']
                                if entry['case_id']==case_id),
                           'source_sha256':source_hashes,'channels':9,
                           'rows_per_channel':600,'changed_join_rejected':True,
                           'preexisting_channels_rejected':True})
    proof = {'format':'c110454-600-source-derived-channels-v1',
             'selected':False,'accepted':False,'manifest_sha256':sha(MANIFEST),
             'cases':checks,'bundle_finalizer_sha256':finalizer_hashes,
             'scope':'synthetic source rows and exact bundled finalizer only'}
    output = HERE / 'draft-600-source-channels-proof.json'
    output.write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'proof_sha256':sha(output),'cases':len(checks),'passed':True}))


if __name__ == '__main__':
    main()
