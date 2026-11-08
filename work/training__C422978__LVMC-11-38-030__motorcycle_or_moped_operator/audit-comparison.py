"""Independent raw-row audit of C422978 synthetic controlled comparisons."""
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


def overlap(packet):
    return sum(row['speed_mps'] > .1 and
               min(point[1] for point in row['body_native_xy_m']) < 5.5 and
               max(point[1] for point in row['body_native_xy_m']) > 3.5
               for row in packet)


def audit():
    proof_path = HERE / 'synthetic-controlled-comparison.json'
    proof = read(proof_path)
    manifest = read(HERE / 'draft-execution-manifest.json')
    full = read(HERE / 'full-package-summary.json')
    assert proof['case_plan_sha256'] == sha(HERE / 'case-plan.json')
    assert proof['manifest_sha256'] == sha(HERE / 'draft-execution-manifest.json')
    assert proof['full_package_summary_sha256'] == sha(HERE / 'full-package-summary.json')
    assert len(proof['rows']) == 4 and not proof['selected_or_original_claimed']
    assert len(full['results']) == 8 and full['manifest_sha256'] == proof['manifest_sha256']
    audited = []
    for row in proof['rows']:
        candidate = row['candidate_id']
        assert candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')
        left = HERE / 'native/saved-fixtures/witness_1' / candidate
        right = HERE / 'native/saved-fixtures/witness_2' / candidate
        a, b = lines(left / 'native-observed.jsonl'), lines(right / 'native-observed.jsonl')
        assert len(a) == len(b) == 480
        for index, (roadway, sidewalk) in enumerate(zip(a, b)):
            assert roadway['frame'] == sidewalk['frame'] == index
            assert roadway['native_frame'] == sidewalk['native_frame'] == 1000 + index
            assert roadway['time_s'] == sidewalk['time_s'] == index / 20
            assert roadway['motorcycle_blueprint'] == sidewalk['motorcycle_blueprint'] == 'vehicle.kawasaki.ninja'
            assert roadway['speed_mps'] == sidewalk['speed_mps'] == 4.0
            assert roadway['center_native_xy_m'][0] == sidewalk['center_native_xy_m'][0]
        for source in ('native-map-readback.json', 'video_frames.jsonl', 'capture/evidence.jsonl'):
            assert sha(left / source) == sha(right / source)
        expected = row['positive']
        assert expected['fixed_frame_count'] == 480
        assert expected['roadway_overlap_frames'] == overlap(a) == 0
        assert expected['sidewalk_overlap_frames'] == overlap(b) >= 390
        assert expected['difference_frames'] == overlap(b) - overlap(a)
        for case, folder in (('witness_1', left), ('witness_2', right)):
            for name, checksum in expected['source_hashes'][case].items():
                assert checksum == sha(folder / name)
            entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + case))
            ref = entry if candidate == 'primary' else next(
                x for x in entry['candidates'] if x['id'] == candidate)
            assert ref['construction_sha256'] == sha(HERE / ref['construction'])
            package = next(r for r in full['results'] if r['case_id'] == entry['case_id']
                           and r['candidate_id'] == candidate)
            assert package['construction_sha256'] == ref['construction_sha256']
        assert len(row['negatives']) == 2
        assert {n['kind'] for n in row['negatives']} == {'changed_speed', 'changed_frame_map'}
        assert all(n['rejected'] and n['reason'].startswith('Measured source hash differs:')
                   for n in row['negatives'])
        for negative in row['negatives']:
            source = 'native-observed.jsonl' if negative['kind'] == 'changed_speed' else 'video_frames.jsonl'
            altered = lines(right / source)
            if negative['kind'] == 'changed_speed':
                altered[90]['speed_mps'] = 5.0
            else:
                altered[90]['native_frame'] += 1
            packet = ''.join(json.dumps(item, sort_keys=True) + '\n' for item in altered).encode()
            assert negative['mutated_source_sha256'] == hashlib.sha256(packet).hexdigest()
            assert negative['reason'] == 'Measured source hash differs: ' + source
        audited.append({'candidate_id': candidate, 'roadway_overlap_frames': overlap(a),
                        'sidewalk_overlap_frames': overlap(b)})
    output = {'format': 'c422978-independent-controlled-comparison-audit-v1',
              'proof_sha256': sha(proof_path), 'audited': audited,
              'synthetic_only': True, 'selected_or_original_claimed': False}
    (HERE / 'synthetic-controlled-comparison-audit.json').write_text(json.dumps(output, indent=2) + '\n')
    return output


if __name__ == '__main__':
    print(json.dumps({'audited': len(audit()['audited'])}))
