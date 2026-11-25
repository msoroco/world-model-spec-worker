"""Independently audit selected motorcycle pairs and their fixed conditions."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANDIDATES = ('primary', 'fallback1', 'fallback2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def audit(diagnostic, tamper):
    if not diagnostic:
        raise ValueError('Original Native source required for accepted comparison')
    manifest = read(HERE / 'selected-30s-draft-execution-manifest.json')
    if len(manifest['cases']) != 2:
        raise ValueError('Comparison requires exactly two selected cases')
    rows = []
    for candidate in CANDIDATES:
        paired = []
        for witness, entry in zip(('witness_1', 'witness_2'), manifest['cases']):
            if not entry['case_id'].endswith('__' + witness):
                raise ValueError('Comparison cases reversed')
            selected = entry if candidate == 'primary' else next(x for x in entry['candidates'] if x['id'] == candidate)
            path = HERE / selected['construction']
            if sha(path) != selected['construction_sha256']:
                raise ValueError('Comparison construction changed')
            construction = read(path)
            files = {item['path']: item['content'] for item in construction['files']}
            config = json.loads(files['config.json'])
            tracks = [json.loads(line) for line in files['requested-tracks.jsonl'].splitlines()]
            receipt_path = HERE / 'selected-30s/proof' / witness / candidate / 'compatibility.json'
            receipt = read(receipt_path)
            if (receipt['construction_sha256'] != selected['construction_sha256'] or
                    receipt['candidate_id'] != candidate or not receipt['passed']):
                raise ValueError('Selected compatibility source changed')
            metric = receipt['measurement_examples']['motorcycle_sidewalk_occupancy']['value']
            if tamper == 'city_boundary' and witness == 'witness_2':
                metric['source_hashes']['city-context.json'] = '0' * 64
            if tamper == 'speed' and witness == 'witness_2':
                tracks[10]['requested_speed_mps'] = 5.0
            if tamper == 'frame_map' and witness == 'witness_2':
                metric['source_hashes']['video_frames.jsonl'] = '0' * 64
            paired.append((entry, config, tracks, metric, receipt_path))
        (first_entry, first, first_track, first_metric, first_receipt), (second_entry, second, second_track, second_metric, second_receipt) = paired
        for key in ('actor', 'cell_id', 'law_id', 'duration_s', 'rate_hz', 'road_sha256',
                    'assignment_sha256', 'cameras', 'required_atoms', 'source_packets', 'policy'):
            if first[key] != second[key]:
                raise ValueError('Fixed comparison condition changed: ' + key)
        if len(first_track) != len(second_track) or len(first_track) != 600:
            raise ValueError('Fixed comparison window changed')
        for i, (a, b) in enumerate(zip(first_track, second_track)):
            if (a['frame'] != b['frame'] or a['frame'] != i or
                    a['time_s'] != b['time_s'] or
                    a['motorcycle_blueprint'] != b['motorcycle_blueprint'] or
                    a['requested_speed_mps'] != b['requested_speed_mps'] or
                    a['requested_body_width_m'] != b['requested_body_width_m'] or
                    a['requested_center_xy_m'][0] != b['requested_center_xy_m'][0]):
                raise ValueError('Fixed motorcycle frame/identity/speed/path changed')
        for source in ('native-map-readback.json', 'video_frames.jsonl',
                       'city-context.json'):
            if first_metric['source_hashes'][source] != second_metric['source_hashes'][source]:
                raise ValueError('Fixed saved source changed: ' + source)
        expected = 520
        if (first_metric['moving_sidewalk_overlap_frames'] != 0 or
                second_metric['moving_sidewalk_overlap_frames'] != expected or
                first_metric['spatial_context']['city_authority_reviewed'] is not False or
                second_metric['spatial_context']['city_authority_reviewed'] is not False):
            raise ValueError('Paired sidewalk occupancy or City uncertainty differs')
        requested_overlap = sum(row['requested_center_xy_m'][1] - row['requested_body_width_m'] / 2 < -3.5
                                and row['requested_center_xy_m'][1] + row['requested_body_width_m'] / 2 > -5.5
                                for row in second_track)
        expected_requested = 535 if candidate == 'fallback1' else 512 if candidate == 'fallback2' else 520
        if requested_overlap != expected_requested:
            raise ValueError('Authored sidewalk contrast differs')
        rows.append({'candidate_id': candidate,
                     'case_ids': [first_entry['case_id'], second_entry['case_id']],
                     'moving_sidewalk_overlap_frames': [0, expected],
                     'requested_sidewalk_overlap_frames': [0, requested_overlap],
                     'compatibility_sha256': [sha(first_receipt), sha(second_receipt)],
                     'joined_frames': 600})
    return {'format': 'c422978-selected-comparison-audit-v1', 'rows': rows,
            'diagnostic_only': True, 'original_native_observed': False,
            'city_authority_reviewed': False, 'legal_verdict': None,
            'passed': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--tamper', choices=('city_boundary', 'speed', 'frame_map'))
    args = parser.parse_args()
    print(json.dumps(audit(args.diagnostic, args.tamper), sort_keys=True))
