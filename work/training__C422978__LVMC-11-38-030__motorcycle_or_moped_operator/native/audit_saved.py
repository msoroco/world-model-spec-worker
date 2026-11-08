"""Independent raw-row audit of the C422978 synthetic saved occupancy proof."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    proof = read(HERE / 'saved-proof.json')
    assert proof['format'] == 'c422978-synthetic-saved-proof-v1'
    assert proof['processor_sha256'] == sha(HERE / 'measure_saved.py')
    assert proof['request_manifest_sha256'] == sha(HERE / 'drafts/manifest.json')
    assert len(proof['positives']) == 8 and len(proof['negatives']) == 4
    assert not proof['original_native_processed'] and proof['legal_verdict'] is None
    audited = []
    for item in proof['positives']:
        case, candidate = item['case_suffix'], item['candidate_id']
        folder = HERE / 'saved-fixtures' / case / candidate
        report = read(folder / 'analysis-report.json')
        assert item['analysis_sha256'] == sha(folder / 'analysis-report.json')
        assert report['source_hashes'] == item['source_hashes']
        for name, checksum in item['source_hashes'].items():
            assert checksum == sha(folder / name)
        observed = lines(folder / 'native-observed.jsonl')
        mapping = lines(folder / 'video_frames.jsonl')
        evidence = lines(folder / 'capture/evidence.jsonl')
        assert len(observed) == len(mapping) == len(evidence) == 480
        overlaps, inside = [], []
        for index, (row, video, captured) in enumerate(zip(observed, mapping, evidence)):
            assert row['frame'] == video['video_frame'] == index
            assert row['native_frame'] == video['native_frame'] == captured['original_frame'] == 1000 + index
            assert abs(row['time_s'] - index/20) < 1e-6
            assert abs(video['time_s'] - row['time_s']) < 1e-6
            assert abs(captured['recording_time_s'] - row['time_s']) < 1e-6
            assert row['motorcycle_blueprint'] == 'vehicle.kawasaki.ninja'
            body = row['body_native_xy_m']
            assert len(body) == 4
            assert abs(sum(v[1] for v in body)/4 - row['center_native_xy_m'][1]) < .01
            if row['speed_mps'] > .1 and min(v[1] for v in body) < 5.5 and max(v[1] for v in body) > 3.5:
                overlaps.append(index)
            if row['speed_mps'] > .1 and min(v[1] for v in body) >= 3.5 and max(v[1] for v in body) <= 5.5:
                inside.append(index)
        assert len(overlaps) == report['moving_sidewalk_overlap_frames'] == item['moving_sidewalk_overlap_frames']
        assert len(inside) == report['full_body_inside_sidewalk_frames']
        assert (overlaps[0] if overlaps else None) == report['first_moving_sidewalk_overlap_frame']
        assert bool(overlaps) == (case == 'witness_2')
        assert not report['city_sidewalk_verified'] and report['legal_verdict'] is None
        audited.append({'case_suffix': case, 'candidate_id': candidate,
                        'analysis_sha256': item['analysis_sha256']})
    assert not (HERE / 'saved-fixtures/negative/missing_actor/native-observed.jsonl').exists()
    assert lines(HERE / 'saved-fixtures/negative/frame_join/video_frames.jsonl')[90]['native_frame'] == 2000
    assert lines(HERE / 'saved-fixtures/negative/body_center/native-observed.jsonl')[90]['body_native_xy_m'][0][1] == -20
    assert lines(HERE / 'saved-fixtures/negative/identity/native-observed.jsonl')[90]['motorcycle_blueprint'] == 'vehicle.tesla.model3'
    output = {'format': 'c422978-independent-saved-audit-v1',
              'saved_proof_sha256': sha(HERE / 'saved-proof.json'),
              'audited_positives': audited, 'audited_negatives': 4,
              'original_native_or_legal_outcome_claimed': False}
    (HERE / 'saved-audit.json').write_text(json.dumps(output, indent=2) + '\n')
    return output


if __name__ == '__main__':
    print(json.dumps({'audited': len(audit()['audited_positives'])}))
