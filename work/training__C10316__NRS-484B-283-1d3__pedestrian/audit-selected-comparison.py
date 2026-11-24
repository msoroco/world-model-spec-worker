"""Independent fixed-condition and one-variable check for selected pair."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c10316-head-refresh-v5'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    if len(manifest['cases']) != 2:
        raise ValueError('Exact selected comparison needs two cases')
    specs = [json.loads((HERE / f'diagnostic30-controlled_{index}.json').read_text())
             for index in (1, 2)]
    left, right = specs
    fixed_files = ('trace.jsonl', 'capture/evidence.jsonl', 'capture/native/frames.jsonl',
                   'video_frames.jsonl')
    for name in fixed_files:
        if left['files'][name] != right['files'][name]:
            raise ValueError('Controlled motion or frame map differs: ' + name)
    if left['graphs'] != right['graphs'] or left['videos'] != right['videos']:
        raise ValueError('Graph or camera source differs')
    contexts = [json.loads(spec['files']['no-countdown-context.json']) for spec in specs]
    fixed_context = ('source_kind', 'crosswalk_id', 'device_id', 'near_highway_edge_xy_m',
                     'crossing_forward_xy', 'highway_span_m', 'authored_map_sha256',
                     'steady_start_s', 'countdown_present')
    for key in fixed_context:
        if contexts[0].get(key) != contexts[1].get(key):
            raise ValueError('Fixed crossing or signal context differs: ' + key)
    if [c['flash_start_s'] for c in contexts] != [2, .5]:
        raise ValueError('Requested flashing-start comparison differs')
    samples = [rows(spec['files']['no-countdown-samples.jsonl']) for spec in specs]
    if len(samples[0]) != 600 or len(samples[1]) != 600:
        raise ValueError('Full 600-frame source missing')
    fixed_sample = ('native_frame', 'time_s', 'crosswalk_id', 'device_id',
                    'pedestrian_xy_m', 'pedestrian_footprint_xy_m', 'countdown_visible')
    for pair in zip(*samples):
        if any(pair[0].get(key) != pair[1].get(key) for key in fixed_sample):
            raise ValueError('Fixed pedestrian motion or no-countdown status differs')
    measured = []
    for index, entry in enumerate(manifest['cases'], 1):
        folder = SCRATCH / f'controlled_{index}-primary/compat'
        report = json.loads((folder / 'analysis-report.json').read_text())
        value = report['measurements']['no_countdown_entry_and_clearance']['value']
        saved = json.loads((SCRATCH / f'controlled_{index}-primary/saved/v0001/processing.json').read_text())
        if not saved['passed'] or not saved['recorded_only'] or value['first_entry']['first_frame'] != 118 or \
                value['steady_start']['first_frame'] != 280 or value['original_frames'] != 600:
            raise ValueError('Measured entry, steady or saved processing differs')
        measured.append(value['entry_indication'])
    if measured != ['walk', 'dont_walk_flashing']:
        raise ValueError('Measured controlled entry states differ')
    receipt = {'format': 'c10316-selected-comparison-source-audit-v1',
               'passed': True, 'case_ids': [e['case_id'] for e in manifest['cases']],
               'manifest_sha256': sha(HERE / 'execution-manifest.json'),
               'diagnostic_source_sha256': [sha(HERE / f'diagnostic30-controlled_{i}.json')
                                            for i in (1, 2)],
               'fixed_motion_camera_and_map': True,
               'deliberate_difference': 'requested no-countdown flashing start (2.0 s versus 0.5 s)',
               'measured_entry_states': measured,
               'physical_or_legal_acceptance_claimed': False}
    path = HERE / 'head-refresh/selected-comparison.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(sha(path))


if __name__ == '__main__':
    main()
