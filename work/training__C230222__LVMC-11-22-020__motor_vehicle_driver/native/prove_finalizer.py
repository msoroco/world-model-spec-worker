"""Exercise saved curbside finalizer on source-shaped CPU fixtures only."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

from finalize_driving import finalize
from prove_driving_cues import fixture

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT.name + '__probe_a'


def diagnostic(path):
    fixture(path)
    context = path / 'driving-context.json'
    data = json.loads(context.read_text())
    data['case_id'] = CASE
    context.write_text(json.dumps(data, indent=2) + '\n')
    for index in range(600):
        with (path / 'trace.jsonl').open('a') as stream:
            stream.write(json.dumps({'frame': index, 'time_s': index / 20}) + '\n')
    construction = json.loads((ROOT / 'draft-native/probe_a/primary/construction.json').read_text())
    configuration = next(item for item in construction['files']
                         if item['path'] == 'config.json')['content']
    (path / 'config.json').write_text(configuration)
    (path / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n')
    for name in ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                 'driver_reference.mkv'):
        (path / name).write_bytes(b'synthetic-unit-video-placeholder')


def rejected(root, label, alter):
    path = root / label
    diagnostic(path)
    alter(path)
    try:
        finalize(path, path / 'analysis.json')
    except (ValueError, KeyError) as error:
        return {'case': label, 'error': str(error)}
    raise AssertionError('Negative source accepted: ' + label)


def main():
    output_root = os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')
    if not output_root or '.runtime-work' not in Path(output_root).parts:
        raise ValueError('Use a scratch output root under .runtime-work')
    with tempfile.TemporaryDirectory(dir=output_root) as temp:
        root = Path(temp)
        good = root / 'good'
        diagnostic(good)
        report = finalize(good, good / 'analysis.json')
        result = json.loads((good / 'result.json').read_text())
        channels = list((good / 'channels').glob('*.jsonl'))
        lines = (good / 'channels/kin.speed.jsonl').read_text().splitlines()
        assert report['case_id'] == result['case_id'] == CASE
        assert len(channels) == 8 and all(len(p.read_text().splitlines()) == 600 for p in channels)
        assert len(lines) == 600 and result['provenance_kind'] == 'synthetic_fixture'
        assert result['measured_values']['legal_carelessness_or_imprudence'] is None
        selected = report['measurements']['curbside_manner_measurement']
        assert selected['method'] == 'measure_curbside'
        assert selected['value']['sample_count'] == 600
        assert set(selected['sources']) == {
            'native-ego-frames.jsonl', 'native-body-geometry.jsonl',
            'native-collision-events.jsonl', 'video_frames.jsonl',
            'driving-context.json', 'trace.jsonl'}
        for source, digest in selected['sources'].items():
            assert hashlib.sha256((good / source).read_bytes()).hexdigest() == digest
        negatives = [
            rejected(root, 'missing_body', lambda p: (p / 'native-body-geometry.jsonl').unlink()),
            rejected(root, 'missing_video', lambda p: (p / 'overview.mkv').unlink()),
            rejected(root, 'wrong_case', lambda p: (p / 'driving-context.json').write_text(
                json.dumps({**json.loads((p / 'driving-context.json').read_text()),
                            'case_id': 'wrong'}) + '\n')),
        ]
        try:
            finalize(good, good / 'second-analysis.json')
        except ValueError as error:
            negatives.append({'case': 'repeat_finalization', 'error': str(error)})
        else:
            raise AssertionError('Repeat finalization accepted')
    proof = {'format': 'c230222-saved-finalizer-diagnostic-v1',
             'case_id': CASE, 'source_kind': 'synthetic_native_sample',
             'physical_acceptance_claimed': False,
             'compatibility_claimed': False,
             'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'finalizer_sha256': hashlib.sha256((ROOT / 'native/finalize_driving.py').read_bytes()).hexdigest(),
             'driving_cues_sha256': hashlib.sha256((ROOT / 'native/driving_cues.py').read_bytes()).hexdigest(),
             'body_geometry_sha256': hashlib.sha256((ROOT / 'native/body_geometry.py').read_bytes()).hexdigest(),
             'positive': {'source_joined_rows': 600, 'channel_count': 8,
                          'result_emitted': True,
                          'legal_verdict': None}, 'negative': negatives}
    path = ROOT / 'native/finalizer-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'proof': str(path), 'negative_count': len(negatives),
                      'proof_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
