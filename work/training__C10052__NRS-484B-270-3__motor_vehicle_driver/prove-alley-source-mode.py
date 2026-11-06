"""CPU parser test for shifted original-style IDs, without physical claims."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
from measure_alley_transition import measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_rows(path,values):
    path.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in values))


def manifest(folder):
    (folder/'alley-transition-sources.json').write_text(json.dumps({
        'format':'c10052-alley-transition-sources-v1',
        'source_kind':'original_native',
        'sha256':{name:sha(folder/name) for name in
                  ('native_samples.jsonl','road_geometry.json')}})+'\n')


def run():
    prior = json.loads((HERE/'alley-transition-summary.json').read_text())
    source = REPO/prior['source_root']/'near_alley'
    root = Path(tempfile.mkdtemp(dir=REPO/'.runtime-work',prefix='c10052-alley-source-mode-'))
    positive = root/'positive';positive.mkdir()
    shutil.copyfile(source/'road_geometry.json',positive/'road_geometry.json')
    values = rows(source/'native_samples.jsonl')
    for i,row in enumerate(values):
        row['native_frame'] = 5010+i
        row['time_s'] = round(8.05+i/20,6)
        row.pop('synthetic_diagnostic')
    write_rows(positive/'native_samples.jsonl',values)
    manifest(positive)
    result = measure(positive)
    assert result['source_kind'] == 'original_native'
    assert result['first_facility_entry_native_frame'] == 5080
    assert result['first_alley_footprint_native_frame'] == 5111
    assert result['simultaneous_moving_overlap_frames'] == 27
    assert result['statutory_exception_observed'] == 'unresolved'
    assert result['legal_verdict_claimed'] is False and result['accepted'] is False
    negatives=[]
    for name,mutate,expected in (
        ('synthetic_relabel',lambda rs:rs[0].update(synthetic_diagnostic=True),
         'synthetic row labeled original'),
        ('time_drift',lambda rs:rs[200].update(time_s=rs[200]['time_s']+.01),
         'Original alley transition frame/time differs')):
        target = root/name;shutil.copytree(positive,target)
        changed = rows(target/'native_samples.jsonl');mutate(changed)
        write_rows(target/'native_samples.jsonl',changed);manifest(target)
        try:measure(target)
        except ValueError as error:
            assert expected in str(error)
            negatives.append({'name':name,'error':str(error),
                              'samples_sha256':sha(target/'native_samples.jsonl')})
        else:raise AssertionError('Parser negative passed: '+name)
    summary = {'format':'c10052-alley-source-mode-cpu-test-v1',
        'source_root':root.relative_to(REPO).as_posix(),
        'positive_source_hashes':result['source_sha256'],
        'first_facility_entry_native_frame':5080,
        'first_alley_footprint_native_frame':5111,
        'simultaneous_moving_overlap_frames':27,
        'negatives':negatives,
        'source_kind_input':'mock original-style IDs derived from synthetic geometry',
        'physical_observation_claimed':False,'accepted':False}
    (HERE/'alley-source-mode-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':
    print(json.dumps(run(),indent=2))
