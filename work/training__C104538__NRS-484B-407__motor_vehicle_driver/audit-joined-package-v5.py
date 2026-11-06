"""Independent source audit for the unselected C104538 synthetic v1 package."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from traffic_spec_adapter.environment_measurements import load


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def payload(path, header):
    data = path.read_bytes()
    assert data.startswith(header)
    return data[len(header):]


def main():
    scratch = REPO / '.runtime-work/c104538/joined-package-v5'
    fixture, output = scratch / 'fixture', scratch / 'output'
    summary = json.loads((HERE / 'joined-package-probe-summary.json').read_text())
    assert summary['selected'] is False and summary['accepted'] is False
    assert summary['positive']['passed'] is True
    assert summary['negative_removed'] == 'native_body_history.jsonl'
    assert summary['negative_exit_code'] != 0
    assert 'native_body_history.jsonl' in (scratch / 'negative-analysis.log').read_text()
    assert summary['positive']['fixture_manifest']
    calibration = json.loads((fixture / 'environment_calibration.json').read_text())
    surface = json.loads((fixture / 'surface_provenance.json').read_text())
    assert calibration['source_kind'] == surface['source_kind'] == 'synthetic_cpu_fixture'
    assert calibration['original_native_pixels'] is False
    assert calibration['distance_kind'] == 'sampled_lower_bound'
    assert calibration['visibility_m'] == 200
    assert surface['ice_or_snow'] is False
    assert surface['map_sha256'] == sha(fixture / 'road.xodr')
    assert [sample['distance_m'] for sample in calibration['samples']] == [50, 100, 200]
    for sample in calibration['samples']:
        rgb_path = fixture / sample['rgb']['path']
        mask_path = fixture / sample['instance']['path']
        assert sha(rgb_path) == sample['rgb']['sha256']
        assert sha(mask_path) == sample['instance']['sha256']
        rgb = payload(rgb_path, b'P6\n8 8\n255\n')
        mask = payload(mask_path, b'P5\n8 8\n255\n')
        assert len(rgb) == 8*8*3 and len(mask) == 8*8
        target = [rgb[i*3] for i,m in enumerate(mask) if m == 255]
        background = [rgb[i*3] for i,m in enumerate(mask) if m == 0]
        assert len(target) == sample['target_pixels'] == 16
        assert len(background) == 48
        assert set(target) == {90} and set(background) == {180}
        assert (sum(background)/len(background) - sum(target)/len(target))/(sum(background)/len(background)) == sample['weber_contrast'] == 0.5
    trace = rows(fixture / 'trace.jsonl')
    assert len(trace) == 480
    for row in trace:
        m = row['environment_measurements']
        assert m['frame'] == row['frame'] and m['time_s'] == row['time_s']
        assert m['calibration_sha256'] == sha(fixture / 'environment_calibration.json')
        assert m['surface_sha256'] == sha(fixture / 'surface_provenance.json')
        assert m['visibility_m'] == 200 and m['ice_or_snow'] is False
        assert m['weather'] == calibration['weather']
    assert load(fixture) is not None
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work/c104538') as root:
        negative = Path(root)
        for name in ('environment_calibration.json','surface_provenance.json',
                     'surface-declaration.json','asset_relocations.json','road.xodr'):
            shutil.copyfile(fixture / name, negative / name)
        shutil.copytree(fixture / 'environment-calibration',negative / 'environment-calibration')
        target = negative / calibration['samples'][0]['rgb']['path']
        data = bytearray(target.read_bytes());data[-1] ^= 1;target.write_bytes(data)
        try:
            load(negative)
        except ValueError as error:
            assert 'Environmental image source hash mismatch' in str(error)
        else:
            raise AssertionError('Changed calibration image accepted')
    core = json.loads((output / 'converted/adapter_report.json').read_text())
    assert core['atom_coverage']['passed'] is True
    assert core['atom_coverage']['missing'] == []
    assert (output / 'final-decode.json').is_file()
    print(json.dumps({'passed': True, 'frames': 480,
        'case_id': summary['case_id'], 'candidate_id': summary['candidate_id'],
        'calibration_sha256': sha(fixture / 'environment_calibration.json'),
        'surface_sha256': sha(fixture / 'surface_provenance.json'),
        'positive_receipt_sha256': sha(output / 'compatibility.json'),
        'negative_log_sha256': sha(scratch / 'negative-analysis.log'),
        'changed_image_rejected': True,
        'scope': 'unselected synthetic v1 software compatibility; retained visibility rays and synthetic palette are not case-original observations'},sort_keys=True))


if __name__ == '__main__':
    main()
