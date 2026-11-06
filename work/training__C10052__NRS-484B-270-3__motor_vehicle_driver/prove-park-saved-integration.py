"""Exercise the exact saved finalizer with a synthetic parking-control source."""
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE/'native'))
sys.path.insert(0, str(ROOT/'runtime/pipeline/scenario_pipeline'))
from finalize import finalize_full_attempt

spec = importlib.util.spec_from_file_location('saved_fixture', HERE/'saved-fixture-proof.py')
saved_fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(saved_fixture)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(attempt):
    saved_fixture.make_base(attempt, 'probe_b')
    poses = saved_fixture.rows(attempt/'native_samples.jsonl')
    controls = []
    for i, pose in enumerate(poses):
        controls.append({'native_frame':pose['native_frame'], 'time_s':pose['time_s'],
                         'throttle':0.0, 'brake':0.5 if 132 <= i < 479 else 0.0,
                         'hand_brake':160 <= i < 440,
                         'control_source':'synthetic_fixture',
                         'synthetic_diagnostic':True})
    saved_fixture.write_rows(attempt/'native_controls.jsonl', controls)
    names = ('native_samples.jsonl','native_controls.jsonl','road_geometry.json')
    (attempt/'park-act-sources.json').write_text(json.dumps({
        'format':'c10052-park-act-sources-v1', 'source_kind':'synthetic_cpu_fixture',
        'sha256':{name:sha(attempt/name) for name in names}},sort_keys=True)+'\n')


def main():
    media_tools = ROOT/'.runtime-work'/'linux_arm64'
    if not (media_tools/'ffmpeg').is_file() or not (media_tools/'ffprobe').is_file():
        raise RuntimeError('Private CPU ffmpeg/ffprobe tools missing')
    os.environ['PATH'] = str(media_tools) + os.pathsep + os.environ.get('PATH','')
    base = ROOT/'.runtime-work'/'c10052-park-saved-integration'
    base.mkdir(parents=True,exist_ok=True)
    import tempfile
    with tempfile.TemporaryDirectory(dir=base,prefix='run-') as temporary:
        scratch = Path(temporary)
        positive, negative = scratch/'positive',scratch/'negative'
        build(positive)
        build(negative)
        before = saved_fixture.source_hashes(positive)
        report = finalize_full_attempt(positive,positive/'analysis-report.json')
        if saved_fixture.source_hashes(positive) != before:
            raise AssertionError('Saved finalizer changed original sources')
        measurement = report['measurements']['parking_control_observation']
        value = measurement['value']
        assert value['park_control_candidate'] is True
        assert value['held_duration_s'] == 14.0
        assert value['max_held_facility_overlap_m2'] == 9.36
        assert value['facility_designation_verified'] is False
        assert value['statutory_exceptions_verified'] is False
        assert value['legal_park_verdict_claimed'] is False
        result = json.loads((positive/'result.json').read_text())
        assert result['accepted'] is False and result['legal_verdict_claimed'] is False
        controls = saved_fixture.rows(negative/'native_controls.jsonl')
        controls[200]['hand_brake'] = False
        saved_fixture.write_rows(negative/'native_controls.jsonl',controls)
        try:
            finalize_full_attempt(negative,negative/'analysis-report.json')
        except ValueError as exc:
            assert 'Parking source hash differs: native_controls.jsonl' in str(exc),str(exc)
        else:
            raise AssertionError('Changed original control accepted')
        assert not (negative/'result.json').exists()
        output = {'format':'c10052-park-saved-integration-v1',
                  'positive_measurement':measurement,
                  'original_hashes_unchanged':True,
                  'positive_result_accepted':False,
                  'negative':'changed_control_hash_rejected',
                  'source_kind':'synthetic_cpu_fixture',
                  'selected':False}
        audit_source = base/'audit-sources'
        if audit_source.exists():
            shutil.rmtree(audit_source)
        for variant, folder in (('positive', positive), ('negative', negative)):
            target = audit_source/variant
            target.mkdir(parents=True)
            for name in ('native_samples.jsonl','native_controls.jsonl',
                         'road_geometry.json','park-act-sources.json'):
                shutil.copyfile(folder/name,target/name)
        shutil.copyfile(positive/'analysis-report.json',audit_source/'positive'/'analysis-report.json')
        shutil.copyfile(positive/'result.json',audit_source/'positive'/'result.json')
        (HERE/'park-saved-integration-summary.json').write_text(json.dumps(output,indent=2,sort_keys=True)+'\n')
        print(json.dumps({'positive':value,'negative':output['negative'],'selected':False},sort_keys=True))


if __name__=='__main__':
    main()
