"""Retained 480-frame synthetic crossings for the three C10052 fallback triggers."""
import importlib.util
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / '.runtime-work/c10052/fallback-triggers-v1'
spec = importlib.util.spec_from_file_location('fallback_triggers', HERE/'native/fallback_triggers.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, allow_nan=False)+'\n' for row in rows))


def make(name, suffix, change=None):
    folder = ROOT/name
    folder.mkdir()
    source = HERE/'draft-facility'/suffix/'native_samples.jsonl'
    samples = module.rows(source)
    if change == 'short_lead_in':
        samples = samples[40:] + [dict(samples[-1]) for _ in range(40)]
        for index, sample in enumerate(samples):
            sample['native_frame'] = 100+index
            sample['time_s'] = round((index+1)/20, 5)
    elif change == 'stop_error':
        for sample in samples:
            if sample['speed_mps'] <= .1 and sample['native_center_xy_m'][0] > -20:
                sample['native_center_xy_m'][0] += .4
                for vertex in sample['native_body_xy_m']:
                    vertex[0] += .4
    write_rows(folder/'native_samples.jsonl', samples)
    construction = json.loads((HERE/'draft-candidates'/suffix/'primary/construction.json').read_text())
    config = json.loads(next(row['content'] for row in construction['files']
                             if row['path'] == 'config.json'))
    write(folder/'config.json', config)
    stopped = [i for i, row in enumerate(samples) if row['speed_mps'] <= .1 and row['native_center_xy_m'][0] > -20]
    missing = set(stopped[:30]) if change == 'missing_camera' else set()
    annotations = [{'native_frame':row['native_frame'],'time_s':row['time_s'],
        'synthetic_diagnostic':True,
        'views':{'overview':{'full_body':True,'facility_edge':True},
                 'facility':{'full_body':i not in missing,'facility_edge':True}}}
        for i,row in enumerate(samples)]
    write_rows(folder/'camera_visibility.jsonl', annotations)
    manifest = {'format':'c10052-trigger-sources-v1','source_kind':'synthetic_cpu_fixture',
        'route_survey_passed':True,
        'sha256':{name:module.sha(folder/name) for name in
                  ('native_samples.jsonl','config.json','camera_visibility.jsonl')}}
    write(folder/'trigger-sources.json', manifest)
    return folder


def rejects(folder, changed, expected):
    destination = ROOT/changed
    shutil.copytree(folder, destination)
    if changed == 'changed_pixel_source':
        path = destination/'camera_visibility.jsonl'
        path.write_bytes(path.read_bytes()+b' ')
    else:
        path = destination/'trigger-sources.json'
        value = json.loads(path.read_text())
        value['source_kind'] = 'original_native'
        write(path, value)
    try:
        module.evaluate(destination)
    except ValueError as error:
        if expected not in str(error):
            raise
    else:
        raise AssertionError('Negative source was accepted: '+changed)


def main():
    if ROOT.exists():
        raise ValueError('Retain prior trigger proof')
    ROOT.mkdir(parents=True)
    cases = [('baseline','probe_b',None),('fallback1','probe_b','short_lead_in'),
             ('fallback2','probe_b','stop_error'),('fallback3','probe_b','missing_camera')]
    results = {}
    for name,suffix,change in cases:
        folder = make(name,suffix,change)
        results[name] = module.evaluate(folder)
        write(folder/'measurement.json',results[name])
    base = results['baseline']
    assert base['route_lead_in_before_lateral_shift_m'] >= 15
    assert base['maximum_stationary_target_error_m'] <= .25
    assert base['longest_stationary_duration_s'] >= 2
    assert all(value >= .95 for value in base['stopped_frame_visible_fraction'].values())
    assert not any(base['fallback'+str(i)+'_trigger_measured'] for i in range(1,4))
    for index in range(1,4):
        row = results['fallback'+str(index)]
        assert row['fallback'+str(index)+'_trigger_measured']
        assert all(not row['fallback'+str(other)+'_trigger_measured']
                   for other in range(1,4) if other != index)
    rejects(ROOT/'baseline','changed_pixel_source','Trigger source hash differs')
    rejects(ROOT/'baseline','synthetic_as_original','Synthetic samples cannot be original Native')
    summary = {'format':'c10052-synthetic-fallback-trigger-proof-v1',
        'source_root':ROOT.relative_to(REPO).as_posix(),
        'positive':{name:{'measurement_sha256':module.sha(ROOT/name/'measurement.json'),
                          'source_manifest_sha256':module.sha(ROOT/name/'trigger-sources.json')}
                    for name in results},
        'negative_count':2,'physical_observation_claimed':False}
    write(HERE/'fallback-trigger-summary.json',summary)
    print(json.dumps({'passed':True,'variants':len(results),
        'trigger_crossings':3,'negative_rejections':2},sort_keys=True))


if __name__ == '__main__':
    main()
