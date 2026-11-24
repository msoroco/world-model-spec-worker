"""Exercise 600-frame saved source joins and request-only rejection on CPU."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from prove_saved_entry_measurement import make_source
from saved_source_bridge import VIEWS, join

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c111331-v2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path, values):
    path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in values))


def make(case):
    root = SCRATCH / case
    root.mkdir(parents=True, exist_ok=True)
    source = make_source(contrary=case == 'witness_2')
    samples, mapping = [], []
    digest = hashlib.sha256(b'synthetic-camera-diagnostic').hexdigest()
    for index, frame in enumerate(source['frames']):
        sample = {'video_frame': index, 'native_frame': 2000 + index,
                  'time_s': index / 20, 'pedestrian_id': frame['pedestrian_id'],
                  'pedestrian_xy_m': frame['pedestrian_xy'],
                  'requested_pedestrian_indication': 'dont_walk' if case == 'witness_2' else 'walk',
                  'observed_traffic_signal': {**frame['traffic_signal'], 'source': 'native_readback'},
                  'observed_pedestrian_signal': {**frame['pedestrian_signal'], 'source': 'native_readback'},
                  'synthetic_diagnostic': True}
        samples.append(sample)
        mapping.append({'video_frame': index, 'native_frame': 2000 + index,
                        'time_s': index / 20,
                        'source_rgb_sha256': {name: digest for name in VIEWS}})
    rows(root / 'c111331-native-samples.jsonl', samples)
    rows(root / 'video_frames.jsonl', mapping)
    for name, dimensions in (('overview', '1920x1080'), ('approach', '1280x720'),
                             ('reference_corner', '1280x720'), ('driver_reference', '1280x720')):
        path = root / (name + '.mkv')
        if not path.exists():
            subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                '-n', '-f', 'lavfi', '-i', f'color=c=black:s={dimensions}:r=20:d=30',
                '-frames:v', '600', '-an', '-c:v', 'ffv1', '-threads', '1', str(path)],
                check=True, timeout=120)
    return root, source, samples, mapping


def main():
    outcomes = []
    for case in ('witness_1', 'witness_2'):
        root, source, samples, mapping = make(case)
        result = join(root, source['crosswalk'], source['governing_devices'])
        assert result['decoded_frames'] == 600
        assert result['measurement']['entry_frame'] == 200
        assert result['measurement']['contrary_pedestrian_signal_at_entry'] == (case == 'witness_2')
        assert result['legal_verdict'] is None
        outcomes.append({'case': case, 'source_sha256': result['native_samples_sha256'],
                         'video_map_sha256': result['video_map_sha256'],
                         'decoded_frames': 600,
                         'measurement': result['measurement']})
    root, source, samples, mapping = make('witness_1')
    original = (root / 'c111331-native-samples.jsonl').read_bytes()
    negatives = []
    for name, mutation, expected in (
        ('requested_only', lambda x: x[200].pop('observed_pedestrian_signal'),
         'Observed traffic and pedestrian indications required'),
        ('invented_provenance', lambda x: x[200]['observed_pedestrian_signal'].update(source='requested_setting'),
         'Signal indication lacks observed Native provenance'),
        ('wrong_head', lambda x: x[200]['observed_pedestrian_signal'].update(id='other'),
         'governing pedestrian signal sample missing')):
        altered = copy.deepcopy(samples)
        mutation(altered)
        rows(root / 'c111331-native-samples.jsonl', altered)
        try:
            join(root, source['crosswalk'], source['governing_devices'])
        except ValueError as error:
            assert expected in str(error), (name, error)
            negatives.append({'case': name, 'rejected': str(error)})
        else:
            raise AssertionError(name + ' was accepted')
    (root / 'c111331-native-samples.jsonl').write_bytes(original)
    receipt = {'format': 'c111331-saved-source-bridge-cpu-proof-v1', 'passed': True,
               'positive_cases': outcomes, 'negative_rejections': negatives,
               'bridge_sha256': sha(HERE / 'saved_source_bridge.py'),
               'measurement_sha256': sha(HERE / 'saved_entry_measurement.py'),
               'synthetic_diagnostic': True, 'original_native_observed': False,
               'actual_signal_pixels_reviewed': False, 'legal_verdict': None}
    path = HERE / 'saved-source-bridge-proof.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'positives': len(outcomes),
                      'negatives': len(negatives), 'receipt_sha256': sha(path)}))


if __name__ == '__main__':
    main()
